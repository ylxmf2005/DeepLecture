"""
Read-Aloud Use Case.

Streams TTS audio of note content sentence-by-sentence via SSE signaling.
Supports optional translation when the note language differs from the target
playback language.

Pipeline: Load notes → Filter markdown → (Translate) → TTS per sentence → Cache → SSE signal
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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


def _channel(content_id: str) -> str:
    """SSE channel key for read-aloud events."""
    return f"read_aloud:{content_id}"


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

    def generate_stream(self, request: ReadAloudRequest) -> None:
        """
        Main pipeline — runs in a background thread.

        Publishes SSE events to ``read_aloud:{content_id}`` channel:
        - read_aloud_meta (first)
        - paragraph_start / sentence_ready / paragraph_end (per paragraph)
        - read_aloud_complete (last)
        """
        channel = _channel(request.content_id)
        try:
            self._run(request, channel)
        except Exception:
            logger.exception("Read-aloud failed for %s", request.content_id)
            self._publish(channel, "read_aloud_error", {"error": "generation_failed"})

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run(self, req: ReadAloudRequest, channel: str) -> None:
        # 1. Load notes
        result = self._notes.load(req.content_id)
        if not result:
            self._publish(channel, "read_aloud_error", {"error": "notes_not_found"})
            return

        markdown_content, _ = result

        # 2. Filter to speakable paragraphs/sentences
        paragraphs = self._filter.filter_to_sentences(markdown_content)
        if not paragraphs or all(len(p.sentences) == 0 for p in paragraphs):
            self._publish(channel, "read_aloud_error", {"error": "no_speakable_content"})
            return

        # Apply start_paragraph offset
        active_paragraphs = paragraphs[req.start_paragraph :]

        # 3. Publish metadata
        total_sentences = sum(len(p.sentences) for p in active_paragraphs)
        meta = ReadAloudMeta(
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

        # 5. Resolve TTS voice for target language
        voice = self._config.get_voice(req.target_language)

        # 6. Get TTS instance (fallback to config default, typically edge-default)
        tts = self._tts.get(req.tts_model or self._config.tts_model)

        # 7. Process each paragraph
        total_errors = 0

        for para in active_paragraphs:
            self._publish(
                channel,
                "paragraph_start",
                {"paragraph_index": para.index, "title": para.title, "sentence_count": len(para.sentences)},
            )

            for sent_idx, sentence in enumerate(para.sentences):
                sentence_key = f"p{para.index}_s{sent_idx}"
                spoken_text = sentence

                # 7a. Translate if needed
                if needs_translation:
                    try:
                        spoken_text = self._translator.translate(
                            sentence,
                            target_lang=req.target_language,
                            source_lang=req.source_language,
                        )
                    except Exception:
                        logger.warning(
                            "Translation failed for p%d_s%d, using original",
                            para.index,
                            sent_idx,
                        )
                        self._publish(
                            channel,
                            "translation_fallback",
                            {"paragraph_index": para.index, "sentence_index": sent_idx, "reason": "translation_error"},
                        )
                        spoken_text = sentence  # Fallback to original

                # 7b. Synthesize TTS
                try:
                    audio_data = tts.synthesize(spoken_text, voice=voice)
                    if not audio_data:
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

                # 7c. Cache audio
                self._cache.save_audio(req.content_id, sentence_key, audio_data)

                # 7d. Signal sentence ready
                ready = SentenceReady(
                    paragraph_index=para.index,
                    sentence_index=sent_idx,
                    sentence_key=sentence_key,
                    original_text=sentence,
                    spoken_text=spoken_text,
                )
                self._publish(channel, "sentence_ready", dataclasses.asdict(ready))

            self._publish(channel, "paragraph_end", {"paragraph_index": para.index})

        # 8. Signal completion
        complete = ReadAloudComplete(
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
