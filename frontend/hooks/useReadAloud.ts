"use client";

/**
 * useReadAloud — Manages SSE connection, audio queue, and playback state for read-aloud.
 *
 * State machine:  IDLE → LOADING → PLAYING ⇄ PAUSED → IDLE
 *
 * Flow:
 * 1. User clicks play → opens SSE to /api/read-aloud/stream/{id}
 * 2. Backend synthesizes sentence-by-sentence, pushes `sentence_ready` events
 * 3. Hook fetches each sentence's MP3 via REST and queues it
 * 4. Audio plays sequentially; when one sentence ends, the next starts
 * 5. User can pause/resume, stop, or jump to a paragraph (reconnects SSE)
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
    createReadAloudEventSource,
    getSentenceAudioUrl,
    type ReadAloudMeta,
    type SentenceReady,
    type ReadAloudStreamParams,
} from "@/lib/api/readAloud";
import { camelizeKeys } from "@/lib/api/transform";
import { logger } from "@/shared/infrastructure";

const log = logger.scope("useReadAloud");

export type ReadAloudState = "idle" | "loading" | "playing" | "paused";

interface SentenceItem {
    paragraphIndex: number;
    sentenceIndex: number;
    sentenceKey: string;
    originalText: string;
    spokenText: string;
    audioUrl: string;
}

export interface UseReadAloudReturn {
    /** Current playback state */
    state: ReadAloudState;
    /** Metadata from the SSE stream (paragraph structure) */
    meta: ReadAloudMeta | null;
    /** All sentences received so far */
    sentences: SentenceItem[];
    /** Index of the currently playing sentence in the sentences array */
    currentIndex: number;
    /** Total sentences expected */
    totalSentences: number;
    /** Number of sentences ready (received from SSE) */
    readySentences: number;
    /** Error message if any */
    error: string | null;

    /** Start or resume playback */
    play: (params: ReadAloudStreamParams) => void;
    /** Pause playback */
    pause: () => void;
    /** Resume from paused */
    resume: () => void;
    /** Stop playback and close SSE */
    stop: () => void;
    /** Jump to a specific paragraph (reconnects SSE) */
    jumpToParagraph: (params: ReadAloudStreamParams, paragraphIndex: number) => void;
}

// Parse SSE data — backend sends flat JSON with snake_case keys
// EventSource bypasses Axios, so we need manual camelCase conversion
function parseSSEData<T>(event: MessageEvent): T | null {
    try {
        const raw = JSON.parse(event.data);
        return camelizeKeys(raw) as T;
    } catch {
        log.warn("Failed to parse SSE data", { raw: event.data });
        return null;
    }
}

function extractEventType(event: MessageEvent): string | null {
    try {
        const raw = JSON.parse(event.data);
        return raw.event ?? null;
    } catch {
        return null;
    }
}

export function useReadAloud(): UseReadAloudReturn {
    const [state, setState] = useState<ReadAloudState>("idle");
    const [meta, setMeta] = useState<ReadAloudMeta | null>(null);
    const [sentences, setSentences] = useState<SentenceItem[]>([]);
    const [currentIndex, setCurrentIndex] = useState(-1);
    const [totalSentences, setTotalSentences] = useState(0);
    const [error, setError] = useState<string | null>(null);

    const eventSourceRef = useRef<EventSource | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const isPausedRef = useRef(false);
    // Track the latest sentences for use in audio callbacks
    const sentencesRef = useRef<SentenceItem[]>([]);
    const currentIndexRef = useRef(-1);
    // Ref to break the self-reference in playSentenceAt (avoids react-hooks/immutability)
    const playSentenceAtRef = useRef<(index: number, list: SentenceItem[]) => void>(() => {});

    // Keep refs in sync
    useEffect(() => {
        sentencesRef.current = sentences;
    }, [sentences]);
    useEffect(() => {
        currentIndexRef.current = currentIndex;
    }, [currentIndex]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            eventSourceRef.current?.close();
            if (audioRef.current) {
                audioRef.current.pause();
                audioRef.current.src = "";
            }
        };
    }, []);

    const closeSSE = useCallback(() => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
    }, []);

    const stopAudio = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.src = "";
        }
    }, []);

    /** Play the sentence at the given index */
    const playSentenceAt = useCallback((index: number, sentenceList: SentenceItem[]) => {
        const sentence = sentenceList[index];
        if (!sentence) return;

        if (!audioRef.current) {
            audioRef.current = new Audio();
        }

        const audio = audioRef.current;

        audio.onended = () => {
            const nextIndex = currentIndexRef.current + 1;
            const latestSentences = sentencesRef.current;

            if (nextIndex < latestSentences.length) {
                // Play next available sentence
                setCurrentIndex(nextIndex);
                currentIndexRef.current = nextIndex;
                playSentenceAtRef.current(nextIndex, latestSentences);
            } else if (nextIndex >= (meta?.totalSentences ?? latestSentences.length)) {
                // All sentences done
                setState("idle");
                log.info("Read-aloud completed");
            } else {
                // Next sentence not yet received from SSE — wait for it
                // The SSE handler will trigger playback when it arrives
                log.debug("Waiting for next sentence", { nextIndex });
            }
        };

        audio.onerror = () => {
            log.warn("Audio playback error for sentence", { index, key: sentence.sentenceKey });
            // Skip to next
            audio.onended?.(new Event("ended") as unknown as Event);
        };

        audio.src = sentence.audioUrl;
        audio.play().catch((err) => {
            log.warn("Audio play() rejected", { error: err });
        });

        setCurrentIndex(index);
        currentIndexRef.current = index;
        setState("playing");
    }, [meta?.totalSentences]);

    // Keep playSentenceAtRef in sync
    useEffect(() => {
        playSentenceAtRef.current = playSentenceAt;
    }, [playSentenceAt]);

    /** Open SSE connection and start listening */
    const startSSE = useCallback(
        (params: ReadAloudStreamParams, contentId: string) => {
            closeSSE();

            const es = createReadAloudEventSource(params);
            eventSourceRef.current = es;

            es.onmessage = (event: MessageEvent) => {
                const eventType = extractEventType(event);

                switch (eventType) {
                    case "read_aloud_meta": {
                        const data = parseSSEData<ReadAloudMeta>(event);
                        if (data) {
                            setMeta(data);
                            setTotalSentences(data.totalSentences);
                            log.info("Read-aloud meta received", {
                                paragraphs: data.totalParagraphs,
                                sentences: data.totalSentences,
                            });
                        }
                        break;
                    }

                    case "sentence_ready": {
                        const data = parseSSEData<SentenceReady>(event);
                        if (data) {
                            const item: SentenceItem = {
                                ...data,
                                audioUrl: getSentenceAudioUrl(contentId, data.sentenceKey),
                            };

                            setSentences((prev) => {
                                const updated = [...prev, item];
                                sentencesRef.current = updated;

                                // Auto-start playback when first sentence arrives
                                if (updated.length === 1 && !isPausedRef.current) {
                                    setState("playing");
                                    // Start playing in next tick so state is updated
                                    setTimeout(() => playSentenceAt(0, updated), 0);
                                }

                                // If audio is waiting for next sentence, kick it
                                const ci = currentIndexRef.current;
                                if (
                                    ci >= 0 &&
                                    ci === prev.length - 1 &&
                                    !isPausedRef.current &&
                                    audioRef.current?.ended
                                ) {
                                    const nextIdx = prev.length; // = updated.length - 1
                                    setTimeout(() => playSentenceAt(nextIdx, updated), 0);
                                }

                                return updated;
                            });
                        }
                        break;
                    }

                    case "read_aloud_complete": {
                        log.info("SSE: read_aloud_complete");
                        closeSSE();
                        break;
                    }

                    case "read_aloud_error": {
                        const data = parseSSEData<{ error: string }>(event);
                        setError(data?.error ?? "Unknown error");
                        setState("idle");
                        closeSSE();
                        break;
                    }

                    case "sentence_error": {
                        log.warn("Sentence synthesis error", { data: event.data });
                        break;
                    }

                    // paragraph_start, paragraph_end, translation_fallback — informational only
                    default:
                        break;
                }
            };

            es.onerror = () => {
                log.warn("SSE connection error");
                closeSSE();
                // Don't set error state if we already have sentences playing
                if (sentencesRef.current.length === 0) {
                    setError("Connection lost");
                    setState("idle");
                }
            };
        },
        [closeSSE, playSentenceAt]
    );

    // ─── Public API ──────────────────────────────────────────

    const play = useCallback(
        (params: ReadAloudStreamParams) => {
            // Reset state
            setError(null);
            setMeta(null);
            setSentences([]);
            sentencesRef.current = [];
            setCurrentIndex(-1);
            currentIndexRef.current = -1;
            setTotalSentences(0);
            isPausedRef.current = false;
            stopAudio();

            setState("loading");
            startSSE(params, params.contentId);
        },
        [startSSE, stopAudio]
    );

    const pause = useCallback(() => {
        if (audioRef.current && state === "playing") {
            audioRef.current.pause();
            isPausedRef.current = true;
            setState("paused");
        }
    }, [state]);

    const resume = useCallback(() => {
        if (audioRef.current && state === "paused") {
            audioRef.current.play().catch(() => {});
            isPausedRef.current = false;
            setState("playing");
        }
    }, [state]);

    const stop = useCallback(() => {
        closeSSE();
        stopAudio();
        isPausedRef.current = false;
        setState("idle");
        setCurrentIndex(-1);
        currentIndexRef.current = -1;
    }, [closeSSE, stopAudio]);

    const jumpToParagraph = useCallback(
        (params: ReadAloudStreamParams, paragraphIndex: number) => {
            // Close current connection and start fresh from the target paragraph
            play({ ...params, startParagraph: paragraphIndex });
        },
        [play]
    );

    return {
        state,
        meta,
        sentences,
        currentIndex,
        totalSentences,
        readySentences: sentences.length,
        error,
        play,
        pause,
        resume,
        stop,
        jumpToParagraph,
    };
}
