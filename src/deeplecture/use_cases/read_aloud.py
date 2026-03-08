"""
Read-Aloud Use Case.

Streams TTS audio of note content sentence-by-sentence via SSE signaling.
Supports optional translation when the note language differs from the target
playback language.

Pipeline: Load notes → Filter markdown → (Translate) → TTS per sentence → Cache → SSE signal
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from threading import Event

    from deeplecture.config.settings import ReadAloudConfig
    from deeplecture.use_cases.dto.read_aloud import ReadAloudRequest
    from deeplecture.use_cases.interfaces.events import EventPublisherProtocol
    from deeplecture.use_cases.interfaces.note import NoteStorageProtocol
    from deeplecture.use_cases.interfaces.read_aloud import ReadAloudCacheProtocol
    from deeplecture.use_cases.interfaces.text_filter import TextFilterProtocol
    from deeplecture.use_cases.interfaces.translation import TranslationProviderProtocol
    from deeplecture.use_cases.interfaces.tts_provider import TTSProviderProtocol

from deeplecture.use_cases.dto.read_aloud import (
    ParagraphMeta,
    ReadAloudComplete,
    ReadAloudMeta,
    SentenceReady,
)

logger = logging.getLogger(__name__)


def _channel(content_id: str, session_id: str) -> str:
    """SSE channel key for read-aloud events."""
    return f"read_aloud:{content_id}:{session_id}"


class ReadAloudUseCase:
    """Orchestrates note read-aloud streaming."""

    def __init__(
        self,
        *,
        note_storage: NoteStorageProtocol,
        text_filter: TextFilterProtocol,
        translation_provider: TranslationProviderProtocol,
        tts_provider: TTSProviderProtocol,
        cache: ReadAloudCacheProtocol,
        event_publisher: EventPublisherProtocol,
        config: ReadAloudConfig,
    ) -> None:
        self._notes = note_storage
        self._filter = text_filter
        self._translator = translation_provider
        self._tts = tts_provider
        self._cache = cache
        self._events = event_publisher
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_stream(self, request: ReadAloudRequest, *, stop_event: Event | None = None) -> None:
        """
        Main pipeline — runs in a background thread.

        Publishes SSE events to ``read_aloud:{content_id}`` channel:
        - read_aloud_meta (first)
        - paragraph_start / sentence_ready / paragraph_end (per paragraph)
        - read_aloud_complete (last)
        """
        channel = _channel(request.content_id, request.session_id)
        try:
            self._run(request, channel, stop_event=stop_event)
        except Exception:
            logger.exception("Read-aloud failed for %s", request.content_id)
            self._publish(channel, "read_aloud_error", {"error": "generation_failed"})

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run(self, req: ReadAloudRequest, channel: str, *, stop_event: Event | None = None) -> None:
        if self._should_stop(channel, stop_event):
            self._publish_cancelled(channel, req.session_id)
            return

        # 1. Load notes
        result = self._notes.load(req.content_id)
        if not result:
            self._publish(channel, "read_aloud_error", {"error": "notes_not_found"})
            return

        markdown_content, note_updated_at = result

        # 2. Filter to speakable paragraphs/sentences
        paragraphs = self._filter.filter_to_sentences(markdown_content)
        if not paragraphs or all(len(p.sentences) == 0 for p in paragraphs):
            self._publish(channel, "read_aloud_error", {"error": "no_speakable_content"})
            return

        if req.start_paragraph >= len(paragraphs):
            self._publish(channel, "read_aloud_error", {"error": "invalid_start_paragraph"})
            return

        # Apply start_paragraph offset
        active_paragraphs = paragraphs[req.start_paragraph :]

        # 3. Publish metadata
        total_sentences = sum(len(p.sentences) for p in active_paragraphs)
        meta = ReadAloudMeta(
            session_id=req.session_id,
            total_paragraphs=len(active_paragraphs),
            total_sentences=total_sentences,
            paragraphs=[
                ParagraphMeta(index=p.index, title=p.title, sentence_count=len(p.sentences)) for p in active_paragraphs
            ],
        )
        self._publish(channel, "read_aloud_meta", dataclasses.asdict(meta))

        # 4. Determine if translation is needed
        needs_translation = (
            req.source_language
            and req.target_language
            and req.source_language.lower() != req.target_language.lower()
            and self._translator.is_available()
        )

        # 5. Resolve TTS voice/model
        voice = self._config.get_voice(req.target_language)
        tts_model = req.tts_model or self._config.tts_model
        tts = self._tts.get(tts_model)
        variant_key = self._build_variant_key(
            markdown_content=markdown_content,
            note_updated_at=note_updated_at,
            target_language=req.target_language,
            source_language=req.source_language,
            tts_model=tts_model,
            voice=voice,
        )

        # 6. Process each paragraph
        total_errors = 0

        for para in active_paragraphs:
            if self._should_stop(channel, stop_event):
                self._publish_cancelled(
                    channel,
                    req.session_id,
                    total_paragraphs=len(active_paragraphs),
                    total_sentences=total_sentences,
                    total_errors=total_errors,
                )
                return

            self._publish(
                channel,
                "paragraph_start",
                {"paragraph_index": para.index, "title": para.title, "sentence_count": len(para.sentences)},
            )

            spoken_sentences = list(para.sentences)
            if needs_translation:
                spoken_sentences = self._translate_sentences(
                    para.sentences,
                    target_language=req.target_language,
                    source_language=req.source_language,
                    channel=channel,
                    paragraph_index=para.index,
                )

            for sent_idx, sentence in enumerate(para.sentences):
                if self._should_stop(channel, stop_event):
                    self._publish_cancelled(
                        channel,
                        req.session_id,
                        total_paragraphs=len(active_paragraphs),
                        total_sentences=total_sentences,
                        total_errors=total_errors,
                    )
                    return

                sentence_key = f"p{para.index}_s{sent_idx}"
                spoken_text = spoken_sentences[sent_idx]
                cached_audio = self._cache.load_audio(req.content_id, variant_key, sentence_key)
                cached = cached_audio is not None

                # 6a. Synthesize on cache miss
                if cached_audio is None:
                    try:
                        cached_audio = tts.synthesize(spoken_text, voice=voice)
                        if not cached_audio:
                            raise ValueError("Empty audio returned")
                    except Exception:
                        logger.warning("TTS failed for %s", sentence_key)
                        total_errors += 1
                        self._publish(
                            channel,
                            "sentence_error",
                            {"paragraph_index": para.index, "sentence_index": sent_idx, "error": "tts_failed"},
                        )
                        continue
                    self._cache.save_audio(req.content_id, variant_key, sentence_key, cached_audio)

                # 6b. Signal sentence ready
                ready = SentenceReady(
                    session_id=req.session_id,
                    variant_key=variant_key,
                    paragraph_index=para.index,
                    sentence_index=sent_idx,
                    sentence_key=sentence_key,
                    original_text=sentence,
                    spoken_text=spoken_text,
                    cached=cached,
                )
                self._publish(channel, "sentence_ready", dataclasses.asdict(ready))

            self._publish(channel, "paragraph_end", {"paragraph_index": para.index})

        # 7. Signal completion
        complete = ReadAloudComplete(
            session_id=req.session_id,
            total_paragraphs=len(active_paragraphs),
            total_sentences=total_sentences,
            total_errors=total_errors,
        )
        self._publish(channel, "read_aloud_complete", dataclasses.asdict(complete))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _publish(self, channel: str, event_type: str, data: dict[str, Any]) -> None:
        """Publish an SSE event to the read-aloud channel."""
        self._events.publish(channel, event_type, data)

    def _should_stop(self, channel: str, stop_event: Event | None) -> bool:
        if self._is_cancelled(stop_event):
            return True
        subscriber_count = getattr(self._events, "subscriber_count", None)
        if callable(subscriber_count):
            try:
                return subscriber_count(channel) == 0
            except Exception:
                logger.debug("Failed to query subscriber_count for %s", channel)
        return False

    def _translate_sentences(
        self,
        sentences: list[str],
        *,
        target_language: str,
        source_language: str | None,
        channel: str,
        paragraph_index: int,
    ) -> list[str]:
        try:
            translated = self._translator.translate_batch(
                sentences,
                target_lang=target_language,
                source_lang=source_language,
            )
            if len(translated) != len(sentences):
                raise ValueError("translate_batch returned unexpected item count")
            return [t if t and t.strip() else s for s, t in zip(sentences, translated, strict=False)]
        except Exception:
            logger.warning("Batch translation failed for paragraph %d; using original", paragraph_index)
            self._publish(
                channel,
                "translation_fallback",
                {"paragraph_index": paragraph_index, "reason": "translation_error"},
            )
            return list(sentences)

    @staticmethod
    def _build_variant_key(
        *,
        markdown_content: str,
        note_updated_at: object | None,
        target_language: str,
        source_language: str | None,
        tts_model: str,
        voice: str,
    ) -> str:
        """
        Build a deterministic cache variant key.

        Includes content snapshot and synthesis-affecting parameters so cache hits are
        safe across reruns while remaining reusable for identical runs.
        """
        if note_updated_at is None:
            updated_at = ""
        elif hasattr(note_updated_at, "isoformat"):
            updated_at = str(note_updated_at.isoformat())
        else:
            updated_at = str(note_updated_at)

        content_digest = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()[:16]
        raw = "|".join(
            [
                content_digest,
                updated_at.strip(),
                target_language.strip().lower(),
                (source_language or "").strip().lower(),
                tts_model.strip().lower(),
                voice.strip().lower(),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _is_cancelled(stop_event: Event | None) -> bool:
        return bool(stop_event and stop_event.is_set())

    def _publish_cancelled(
        self,
        channel: str,
        session_id: str,
        *,
        total_paragraphs: int = 0,
        total_sentences: int = 0,
        total_errors: int = 0,
    ) -> None:
        complete = ReadAloudComplete(
            session_id=session_id,
            total_paragraphs=total_paragraphs,
            total_sentences=total_sentences,
            total_errors=total_errors,
            cancelled=True,
        )
        self._publish(channel, "read_aloud_complete", dataclasses.asdict(complete))
