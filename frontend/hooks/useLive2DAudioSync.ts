"use client";

import { useRef, useEffect, useCallback } from "react";
import type { Live2DCanvasHandle } from "@/components/live2d/Live2DCanvas";
import type { VideoPlayerRef } from "@/components/video/VideoPlayer";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("Live2DAudioSync");

export interface UseLive2DAudioSyncParams {
    playerRef: React.RefObject<VideoPlayerRef | null>;
    live2dEnabled: boolean;
    live2dSyncWithVideoAudio: boolean;
    live2dModelPath: string;
    /** When set, voiceover mode is active - connect to audio element instead of video */
    selectedVoiceoverId: string | null;
}

export interface UseLive2DAudioSyncReturn {
    live2dRef: React.MutableRefObject<Live2DCanvasHandle | null>;
    connectLive2DAudio: (videoElement: HTMLVideoElement) => void;
    onLive2DLoad: (handle?: Live2DCanvasHandle) => void;
}

/**
 * Hook to manage Live2D audio lip sync with video/audio element.
 * Provides dual connection mechanism to handle race condition:
 * 1. connectLive2DAudio - called when video player is ready
 * 2. onLive2DLoad - called when Live2D model finishes loading
 *
 * Audio source switching:
 * - When voiceover is NOT active: connects to video element
 * - When voiceover IS active: connects to audio element (voiceover track)
 */
export function useLive2DAudioSync({
    playerRef,
    live2dEnabled,
    live2dSyncWithVideoAudio,
    live2dModelPath,
    selectedVoiceoverId,
}: UseLive2DAudioSyncParams): UseLive2DAudioSyncReturn {
    const live2dRef = useRef<Live2DCanvasHandle | null>(null);

    // Stop any existing lip sync when sync is disabled.
    // Without this, disabling the toggle only prevents NEW connections but leaves the current one running.
    useEffect(() => {
        if (live2dEnabled && live2dSyncWithVideoAudio) return;

        const handle = live2dRef.current;
        if (!handle) return;

        // Avoid spamming stop calls if nothing is running.
        if (handle.isLipSyncActive?.() === false) return;

        handle.stopLipSync?.().catch((error) => {
            log.error("Failed to stop Live2D lip sync", toError(error));
        });
    }, [live2dEnabled, live2dSyncWithVideoAudio]);

    /**
     * Connect Live2D to the appropriate audio source based on current mode
     */
    const connectToCurrentSource = useCallback((handle?: Live2DCanvasHandle) => {
        if (!live2dEnabled || !live2dSyncWithVideoAudio) {
            log.debug("connectToCurrentSource skipped: sync disabled");
            return;
        }

        const effectiveHandle = handle || live2dRef.current;

        if (!effectiveHandle) {
            log.debug("connectToCurrentSource skipped: Live2D not ready");
            return;
        }
        if (!playerRef.current) {
            log.debug("connectToCurrentSource skipped: player not ready");
            return;
        }

        const isVoiceoverActive = playerRef.current.isSyncActive?.();

        if (isVoiceoverActive && selectedVoiceoverId) {
            // Voiceover mode: connect to audio element
            const audioElement = playerRef.current.getAudioElement?.();
            if (!audioElement) {
                log.debug("connectToCurrentSource deferred: audio element not available");
                return;
            }
            log.debug("Connecting to voiceover audio element");
            effectiveHandle.connectAudioForLipSync(audioElement).catch((error) => {
                log.error("Failed to connect voiceover audio to Live2D", toError(error));
            });
        } else {
            // Normal mode: connect to video element
            const videoElement = playerRef.current.getVideoElement?.();
            if (!videoElement) {
                log.debug("connectToCurrentSource deferred: video element not available");
                return;
            }
            log.debug("Connecting to video element audio");
            effectiveHandle.connectAudioForLipSync(videoElement).catch((error) => {
                log.error("Failed to connect video audio to Live2D", toError(error));
            });
        }
    }, [live2dEnabled, live2dSyncWithVideoAudio, playerRef, selectedVoiceoverId]);

    // Reconnect Live2D audio when model changes
    useEffect(() => {
        if (!live2dEnabled || !live2dSyncWithVideoAudio || !live2dRef.current || !playerRef.current) return;

        log.debug("Model changed, reconnecting audio", { model: live2dModelPath });
        connectToCurrentSource();
    }, [live2dModelPath, live2dEnabled, live2dSyncWithVideoAudio, playerRef, connectToCurrentSource]);

    // Switch audio source when voiceover mode changes
    // Uses audio element event listeners to ensure connection happens when audio is actually ready
    useEffect(() => {
        if (!live2dEnabled || !live2dSyncWithVideoAudio || !live2dRef.current || !playerRef.current) return;

        log.debug("Voiceover mode changed", { voiceoverId: selectedVoiceoverId });

        let cancelled = false;
        let retryTimeoutId: ReturnType<typeof setTimeout> | null = null;
        let detachAudioListeners: (() => void) | null = null;
        let attempts = 0;
        const MAX_RETRY_ATTEMPTS = 25; // 25 * 100ms = 2.5s max wait

        const attachAudioListeners = () => {
            if (cancelled || !selectedVoiceoverId) return;

            const audioElement = playerRef.current?.getAudioElement?.();
            if (!audioElement) {
                // Audio element is conditionally rendered in VideoPlayer; retry briefly
                if (attempts++ < MAX_RETRY_ATTEMPTS) {
                    retryTimeoutId = setTimeout(attachAudioListeners, 100);
                } else {
                    log.debug("Audio element not available after max retries");
                }
                return;
            }

            const handleAudioSignal = () => {
                // Only connect when audio is actually playing.
                // Connecting during loadedmetadata/timeout can run outside user gesture,
                // leaving AudioContext suspended and risking "silent" media when using WebAudio routing.
                if (audioElement.paused) {
                    log.debug("Audio not playing yet, deferring Live2D connection");
                    return;
                }
                log.debug("Audio playing, reconnecting Live2D");
                connectToCurrentSource();
            };

            audioElement.addEventListener("play", handleAudioSignal);
            audioElement.addEventListener("playing", handleAudioSignal);

            detachAudioListeners = () => {
                audioElement.removeEventListener("play", handleAudioSignal);
                audioElement.removeEventListener("playing", handleAudioSignal);
            };

            // Try connecting immediately if audio is already playing
            if (!audioElement.paused) {
                log.debug("Audio already playing, connecting immediately");
                connectToCurrentSource();
            }
        };

        if (selectedVoiceoverId) {
            // Voiceover selected: set up audio element listeners
            attachAudioListeners();
        }

        // Small delay fallback to ensure refs are attached after voiceover switch
        const fallbackTimeoutId = setTimeout(() => {
            if (!cancelled) {
                connectToCurrentSource();
            }
        }, 100);

        return () => {
            cancelled = true;
            clearTimeout(fallbackTimeoutId);
            if (retryTimeoutId !== null) {
                clearTimeout(retryTimeoutId);
            }
            detachAudioListeners?.();
        };
    }, [selectedVoiceoverId, live2dEnabled, live2dSyncWithVideoAudio, playerRef, connectToCurrentSource]);

    // Callback to connect Live2D audio (called from player ready handler)
    // This handles the case: video ready first, then Live2D
    const connectLive2DAudio = useCallback(
        (videoElement: HTMLVideoElement) => {
            if (!live2dEnabled || !live2dSyncWithVideoAudio) {
                log.debug("connectLive2DAudio skipped: sync disabled");
                return;
            }
            if (!live2dRef.current) {
                log.debug("connectLive2DAudio deferred: Live2D not ready yet");
                return;
            }

            // Check if we should connect to video or audio based on voiceover state
            const isVoiceoverActive = playerRef.current?.isSyncActive?.();
            if (isVoiceoverActive && selectedVoiceoverId) {
                // In voiceover mode, don't connect to video - wait for audio
                log.debug("connectLive2DAudio: voiceover active, skipping video connection");
                return;
            }

            log.debug("Connecting audio from player ready handler");
            live2dRef.current.connectAudioForLipSync(videoElement).catch((error) => {
                log.error("Failed to connect video audio to Live2D", toError(error));
            });
        },
        [live2dEnabled, live2dSyncWithVideoAudio, playerRef, selectedVoiceoverId]
    );

    // Callback for when Live2D finishes loading (called from Live2DCanvas onLoad)
    // This handles the case: Live2D ready first, video was already ready
    const onLive2DLoad = useCallback((handle?: Live2DCanvasHandle) => {
        // Always update ref when a handle is provided.
        // Live2D model changes can remount the canvas and provide a new handle.
        // Keeping the old (now-dead) handle breaks subsequent lip sync connections.
        if (handle) {
            const previousHandle = live2dRef.current;
            if (previousHandle && previousHandle !== handle) {
                // Best-effort cleanup: don't assume the previous handle is still valid.
                if (previousHandle.isLipSyncActive?.() !== false) {
                    previousHandle.stopLipSync?.().catch((error) => {
                        log.error("Failed to stop previous Live2D lip sync", toError(error));
                    });
                }
            }
            live2dRef.current = handle;
        }

        if (!live2dEnabled || !live2dSyncWithVideoAudio) {
            log.debug("onLive2DLoad: sync disabled, ref updated but skipping connection");
            return;
        }

        // Use effectiveHandle pattern for cleaner logic
        const effectiveHandle = handle ?? live2dRef.current;
        if (!effectiveHandle) {
            log.debug("onLive2DLoad deferred: Live2D ref not available");
            return;
        }

        if (!playerRef.current) {
            log.debug("onLive2DLoad deferred: player not ready yet");
            return;
        }

        log.debug("Live2D loaded, connecting to current audio source");
        connectToCurrentSource(effectiveHandle);
    }, [live2dEnabled, live2dSyncWithVideoAudio, playerRef, connectToCurrentSource]);

    return {
        live2dRef,
        connectLive2DAudio,
        onLive2DLoad,
    };
}
