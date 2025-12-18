"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import type { SyncTimeline, SyncTimelineSegment } from "@/lib/api";
import { logger } from "@/shared/infrastructure";

const log = logger.scope("VoiceoverSync");

/**
 * Playback-side A/V sync hook.
 *
 * Architecture:
 * - Audio is the master clock (voiceover audio)
 * - Video adjusts playbackRate to follow audio timeline
 * - Uses sync_timeline.json to map audio time → video time
 *
 * Formula: video_time = src_start + (audio_time - dst_start) * speed
 */

interface UseVoiceoverSyncOptions {
    /** User playback rate (1.0 = normal, 1.5 = 1.5x) */
    userPlaybackRate?: number;
    /** Drift tolerance in seconds before seeking (default: 0.2) */
    driftTolerance?: number;
    /** Sync tick interval in ms (default: 200) */
    tickIntervalMs?: number;
}

interface UseVoiceoverSyncReturn {
    /** Ref to attach to video element */
    videoRef: React.RefObject<HTMLVideoElement | null>;
    /** Ref to attach to audio element */
    audioRef: React.RefObject<HTMLAudioElement | null>;
    /** Whether sync is currently active */
    isActive: boolean;
    /** Current segment index */
    currentSegmentIndex: number;
    /** Start voiceover sync mode */
    startSync: (timeline: SyncTimeline) => void;
    /** Stop voiceover sync mode (restore original video) */
    stopSync: () => void;
    /** Seek to specific video time (external API - converts to audio time internally) */
    seekToVideoTime: (videoTime: number) => void;
    /** Set user playback rate multiplier */
    setUserRate: (rate: number) => void;
    /** Play both audio and video */
    play: () => Promise<void>;
    /** Pause both audio and video */
    pause: () => void;
    /** Get current video time (always returns video time, even in sync mode) */
    getCurrentVideoTime: () => number;
}

/**
 * Binary search: find last segment where dst_start <= t (audio time lookup)
 */
function findSegmentByAudioTime(segments: SyncTimelineSegment[], audioTime: number): number {
    let lo = 0;
    let hi = segments.length - 1;
    let result = 0;

    while (lo <= hi) {
        const mid = Math.floor((lo + hi) / 2);
        if (segments[mid].dstStart <= audioTime) {
            result = mid;
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }

    return result;
}

/**
 * Binary search: find last segment where src_start <= t (video time lookup)
 */
function findSegmentByVideoTime(segments: SyncTimelineSegment[], videoTime: number): number {
    let lo = 0;
    let hi = segments.length - 1;
    let result = 0;

    while (lo <= hi) {
        const mid = Math.floor((lo + hi) / 2);
        if (segments[mid].srcStart <= videoTime) {
            result = mid;
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }

    return result;
}

/**
 * Map audio time to video time using the timeline segment
 * Formula: video_time = src_start + (audio_time - dst_start) * speed
 * Clamps result to segment's src_end to prevent overshoot
 */
function mapAudioToVideo(
    segments: SyncTimelineSegment[],
    audioTime: number,
    segmentIndex: number
): { videoTime: number; speed: number } {
    const seg = segments[Math.max(0, Math.min(segmentIndex, segments.length - 1))];
    const rawVideoTime = seg.srcStart + (audioTime - seg.dstStart) * seg.speed;
    // Clamp to segment boundaries to prevent overshoot
    const videoTime = clamp(rawVideoTime, seg.srcStart, seg.srcEnd);
    return { videoTime, speed: seg.speed };
}

/**
 * Map video time to audio time (inverse mapping)
 * Formula: audio_time = dst_start + (video_time - src_start) / speed
 * Clamps result to segment's dst_end to prevent overshoot
 */
function mapVideoToAudio(
    segments: SyncTimelineSegment[],
    videoTime: number,
    segmentIndex: number
): number {
    const seg = segments[Math.max(0, Math.min(segmentIndex, segments.length - 1))];
    // Guard against invalid speed (division by zero)
    if (!Number.isFinite(seg.speed) || seg.speed <= 1e-6) {
        return seg.dstStart;
    }
    const rawAudioTime = seg.dstStart + (videoTime - seg.srcStart) / seg.speed;
    // Clamp to segment boundaries to prevent overshoot
    return clamp(rawAudioTime, seg.dstStart, seg.dstEnd);
}

function clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, value));
}

function lerp(current: number, target: number, factor: number): number {
    return current + (target - current) * factor;
}

export function useVoiceoverSync(options: UseVoiceoverSyncOptions = {}): UseVoiceoverSyncReturn {
    const {
        userPlaybackRate: initialUserRate = 1.0,
        driftTolerance = 0.2,
        tickIntervalMs = 200,
    } = options;

    const videoRef = useRef<HTMLVideoElement | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const timelineRef = useRef<SyncTimeline | null>(null);
    const segmentIndexRef = useRef<number>(0);
    const userRateRef = useRef<number>(initialUserRate);
    const isActiveRef = useRef<boolean>(false);
    const tickIdRef = useRef<number | null>(null);
    const pendingStartSyncCleanupRef = useRef<(() => void) | null>(null);
    // Store pre-sync video state to restore when exiting voiceover mode
    const preSyncVideoStateRef = useRef<{ muted: boolean; volume: number } | null>(null);

    const [isActive, setIsActive] = useState(false);
    const [currentSegmentIndex, setCurrentSegmentIndex] = useState(0);

    /**
     * Core sync tick - runs every tickIntervalMs when sync is active
     */
    const tick = useCallback(() => {
        const audio = audioRef.current;
        const video = videoRef.current;
        const timeline = timelineRef.current;

        if (!audio || !video || !timeline || audio.paused) {
            return;
        }

        const segments = timeline.segments;
        if (!segments.length) return;

        const audioTime = audio.currentTime;

        // Find current segment (binary search)
        const newIndex = findSegmentByAudioTime(segments, audioTime);
        if (newIndex !== segmentIndexRef.current) {
            segmentIndexRef.current = newIndex;
            setCurrentSegmentIndex(newIndex);
        }

        // Map audio time to video time
        const { videoTime, speed } = mapAudioToVideo(segments, audioTime, newIndex);
        const drift = video.currentTime - videoTime;

        // Target video rate = segment speed * user rate (audio playback rate already reflects user rate)
        const targetRate = speed * userRateRef.current;

        if (targetRate > 4.0) {
            // Extreme speed needed (TTS too short): skip directly to target time
            video.currentTime = videoTime;
            video.playbackRate = 4.0;
        } else if (targetRate < 0.25) {
            // Extreme slow needed (TTS too long): hold at target time with min rate
            video.currentTime = videoTime;
            video.playbackRate = 0.25;
        } else if (Math.abs(drift) > driftTolerance) {
            // Large drift: seek directly
            video.currentTime = videoTime;
            video.playbackRate = clamp(targetRate, 0.25, 4.0);
        } else {
            // Small drift: smooth rate adjustment
            const smoothedRate = lerp(video.playbackRate, targetRate, 0.6);
            video.playbackRate = clamp(smoothedRate, 0.25, 4.0);
        }
    }, [driftTolerance]);

    /**
     * Start sync tick loop
     */
    const startTickLoop = useCallback(() => {
        if (tickIdRef.current !== null) return;

        const loop = () => {
            if (!isActiveRef.current) return;
            tick();
            tickIdRef.current = window.setTimeout(loop, tickIntervalMs);
        };

        loop();
    }, [tick, tickIntervalMs]);

    /**
     * Stop sync tick loop
     */
    const stopTickLoop = useCallback(() => {
        if (tickIdRef.current !== null) {
            clearTimeout(tickIdRef.current);
            tickIdRef.current = null;
        }
    }, []);

    /**
     * Start voiceover sync mode
     * Preserves current video position by converting video time → audio time
     */
    const startSync = useCallback((timeline: SyncTimeline) => {
        const video = videoRef.current;
        const audio = audioRef.current;

        if (!video || !audio) {
            log.warn("Video or audio ref not attached");
            return;
        }

        // Cancel any previous "wait for metadata" setup to avoid stacking listeners/timeouts
        pendingStartSyncCleanupRef.current?.();
        pendingStartSyncCleanupRef.current = null;

        // Switching timelines/audio: stop the current tick loop first.
        // (We intentionally do NOT restore video state here; switching voiceovers should stay in sync mode.)
        stopTickLoop();

        // Ensure we don't keep old audio playing while reconfiguring.
        audio.pause();

        timelineRef.current = timeline;
        isActiveRef.current = true;
        setIsActive(true);

        // Save pre-sync video state only when ENTERING sync mode.
        // If we overwrite this on voiceover switches, stopSync() will restore to "already muted",
        // effectively breaking exit from voiceover mode.
        if (!preSyncVideoStateRef.current) {
            preSyncVideoStateRef.current = {
                muted: video.muted,
                volume: video.volume,
            };
        }

        // Always keep video muted in sync mode; audio will play the voiceover
        video.muted = true;

        // Apply user playback rate to audio immediately
        audio.playbackRate = clamp(userRateRef.current, 0.25, 4.0);

        // Helper to set up sync after audio is ready
        const setupSync = () => {
            // Preserve current video position: convert video time → audio time
            const currentVideoTime = video.currentTime;
            if (timeline.segments.length > 0) {
                const idx = findSegmentByVideoTime(timeline.segments, currentVideoTime);
                const audioTime = mapVideoToAudio(timeline.segments, currentVideoTime, idx);

                // Set audio to corresponding position
                audio.currentTime = audioTime;

                // Update segment tracking
                segmentIndexRef.current = idx;
                setCurrentSegmentIndex(idx);

                // Set initial video playback rate based on segment speed
                const seg = timeline.segments[idx];
                video.playbackRate = clamp(seg.speed * userRateRef.current, 0.25, 4.0);
            } else {
                segmentIndexRef.current = 0;
                setCurrentSegmentIndex(0);
            }

            // If video was playing, start audio too
            if (!video.paused) {
                audio.play().catch(() => {
                    // Autoplay blocked: rollback to prevent "silent video" state
                    log.warn("Audio play blocked on startSync - rolling back");
                    stopTickLoop();
                    isActiveRef.current = false;
                    timelineRef.current = null;
                    setIsActive(false);
                    // Restore video state
                    const preSyncState = preSyncVideoStateRef.current;
                    if (preSyncState) {
                        video.muted = preSyncState.muted;
                        video.volume = preSyncState.volume;
                        preSyncVideoStateRef.current = null;
                    }
                    video.playbackRate = userRateRef.current;
                    video.pause();
                });
            }

            startTickLoop();
        };

        // Wait for audio metadata before setting currentTime
        if (audio.readyState >= 1) {
            // Metadata already loaded
            setupSync();
        } else {
            let timeoutId: ReturnType<typeof setTimeout> | null = null;

            const cleanup = () => {
                audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
                audio.removeEventListener("error", handleAudioError);
                if (timeoutId) {
                    clearTimeout(timeoutId);
                    timeoutId = null;
                }
                if (pendingStartSyncCleanupRef.current === cleanup) {
                    pendingStartSyncCleanupRef.current = null;
                }
            };

            // Wait for metadata
            const handleLoadedMetadata = () => {
                cleanup();
                // Check if sync is still active - user may have toggled off while waiting
                if (isActiveRef.current) {
                    setupSync();
                }
            };

            // Handle audio load failure - rollback video muted state
            const handleAudioError = () => {
                cleanup();
                log.error("Audio failed to load - rolling back sync mode");
                rollbackSync();
            };

            // Rollback helper
            const rollbackSync = () => {
                stopTickLoop();
                isActiveRef.current = false;
                timelineRef.current = null;
                setIsActive(false);

                const preSyncState = preSyncVideoStateRef.current;
                if (preSyncState) {
                    video.muted = preSyncState.muted;
                    video.volume = preSyncState.volume;
                    preSyncVideoStateRef.current = null;
                } else {
                    video.muted = false;
                }
                video.playbackRate = userRateRef.current;
            };

            audio.addEventListener("loadedmetadata", handleLoadedMetadata);
            audio.addEventListener("error", handleAudioError);
            pendingStartSyncCleanupRef.current = cleanup;

            // Timeout fallback - if audio doesn't load within 5 seconds, rollback
            timeoutId = setTimeout(() => {
                if (audio.readyState < 1 && isActiveRef.current) {
                    cleanup();
                    log.warn("Audio metadata timeout - rolling back sync mode");
                    rollbackSync();
                }
            }, 5000);
        }
    }, [startTickLoop, stopTickLoop]);

    /**
     * Stop voiceover sync mode (restore original video)
     */
    const stopSync = useCallback(() => {
        const video = videoRef.current;
        const audio = audioRef.current;

        pendingStartSyncCleanupRef.current?.();
        pendingStartSyncCleanupRef.current = null;

        stopTickLoop();
        isActiveRef.current = false;
        timelineRef.current = null;
        setIsActive(false);

        if (video) {
            // Restore pre-sync video state instead of forcing unmute
            const preSyncState = preSyncVideoStateRef.current;
            if (preSyncState) {
                video.muted = preSyncState.muted;
                video.volume = preSyncState.volume;
                preSyncVideoStateRef.current = null;
            } else {
                // Fallback: unmute if no saved state (should not happen)
                video.muted = false;
            }
            video.playbackRate = userRateRef.current;
        }

        if (audio) {
            audio.pause();
        }
    }, [stopTickLoop]);

    /**
     * Seek to specific video time (external API)
     * Converts video time → audio time internally when in sync mode
     */
    const seekToVideoTime = useCallback((videoTime: number) => {
        const audio = audioRef.current;
        const video = videoRef.current;
        const timeline = timelineRef.current;

        if (!isActiveRef.current) {
            // Not in sync mode: just seek video directly
            if (video) {
                video.currentTime = videoTime;
            }
            return;
        }

        // In sync mode: convert video time → audio time
        if (timeline && timeline.segments.length > 0) {
            const idx = findSegmentByVideoTime(timeline.segments, videoTime);
            const audioTime = mapVideoToAudio(timeline.segments, videoTime, idx);

            if (audio) {
                audio.currentTime = audioTime;
            }
            if (video) {
                video.currentTime = videoTime;
            }
            segmentIndexRef.current = idx;
            setCurrentSegmentIndex(idx);
        }
    }, []);

    /**
     * Set user playback rate
     * In sync mode, applies to BOTH audio and video to maintain synchronization
     */
    const setUserRate = useCallback((rate: number) => {
        // Store clamped rate to ensure targetRate calculations match actual audio playback
        const clampedRate = clamp(rate, 0.25, 4.0);
        userRateRef.current = clampedRate;
        const video = videoRef.current;
        const audio = audioRef.current;
        const timeline = timelineRef.current;

        if (isActiveRef.current && timeline && timeline.segments.length > 0) {
            // In sync mode: set audio rate to user rate, video rate = segment.speed * user rate
            if (audio) {
                audio.playbackRate = clampedRate;
            }
            if (video) {
                const seg = timeline.segments[segmentIndexRef.current];
                video.playbackRate = clamp(seg.speed * clampedRate, 0.25, 4.0);
            }
        } else if (video) {
            // Not in sync mode: just set video rate
            video.playbackRate = clampedRate;
        }
    }, []);

    /**
     * Play both audio and video
     */
    const play = useCallback(async () => {
        const audio = audioRef.current;
        const video = videoRef.current;

        if (isActiveRef.current) {
            // Sync mode: audio leads
            try {
                if (audio) await audio.play();
                if (video) {
                    // Sync video position before playing
                    const timeline = timelineRef.current;
                    if (timeline && timeline.segments.length > 0) {
                        const audioTime = audio?.currentTime ?? 0;
                        const idx = findSegmentByAudioTime(timeline.segments, audioTime);
                        const { videoTime } = mapAudioToVideo(timeline.segments, audioTime, idx);
                        video.currentTime = videoTime;
                    }
                    await video.play();
                }
                startTickLoop();
            } catch (error) {
                // Handle autoplay blocked by browser
                log.warn("Play blocked by browser", { error: error instanceof Error ? error.message : String(error) });
                // Rollback: pause audio if video play failed to keep them in sync
                if (audio && !audio.paused) {
                    audio.pause();
                }
                throw error; // Re-throw so caller can handle (e.g., show play button)
            }
        } else {
            // Normal mode: just play video
            if (video) await video.play();
        }
    }, [startTickLoop]);

    /**
     * Pause both audio and video
     */
    const pause = useCallback(() => {
        const audio = audioRef.current;
        const video = videoRef.current;

        stopTickLoop();

        if (audio) audio.pause();
        if (video) video.pause();
    }, [stopTickLoop]);

    /**
     * Get current video time (always returns video time, even in sync mode)
     * This is what external consumers (subtitles, timeline, progress) should use
     */
    const getCurrentVideoTime = useCallback(() => {
        return videoRef.current?.currentTime ?? 0;
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            pendingStartSyncCleanupRef.current?.();
            pendingStartSyncCleanupRef.current = null;
            stopTickLoop();
        };
    }, [stopTickLoop]);

    // Handle audio ended event - stop sync and seek video to end
    // Re-run when isActive changes to ensure binding after audio element mounts
    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        const handleAudioEnded = () => {
            if (isActiveRef.current) {
                const video = videoRef.current;
                const timeline = timelineRef.current;

                // Seek video to end before stopping sync
                if (video && timeline && timeline.segments.length > 0) {
                    const lastSeg = timeline.segments[timeline.segments.length - 1];
                    video.currentTime = lastSeg.srcEnd;
                }

                stopSync();
            }
        };

        audio.addEventListener("ended", handleAudioEnded);
        return () => audio.removeEventListener("ended", handleAudioEnded);
    }, [stopSync, isActive]);

    /**
     * Intercept native video controls.
     * When user interacts with native controls (e.g., clicking video to play/pause),
     * mirror state to audio. Re-run when isActive changes to ensure binding.
     */
    useEffect(() => {
        const video = videoRef.current;
        const audio = audioRef.current;
        if (!video || !audio) return;

        const handleVideoPlay = () => {
            if (isActiveRef.current && audio.paused) {
                audio.play().then(() => {
                    startTickLoop();
                }).catch(() => {
                    video.pause();
                });
            } else if (isActiveRef.current && !audio.paused) {
                startTickLoop();
            }
        };

        const handleVideoPause = () => {
            // Ignore pause events triggered by browser background tab optimization
            // Chrome auto-pauses muted videos when tab is hidden
            if (document.hidden) {
                return;
            }
            if (isActiveRef.current && !audio.paused) {
                audio.pause();
                stopTickLoop();
            }
        };

        // Mirror native video seeking to audio timeline
        const handleVideoSeeked = () => {
            if (!isActiveRef.current) return;
            const timeline = timelineRef.current;
            if (!timeline || !timeline.segments.length) return;

            const videoTime = video.currentTime;
            const idx = findSegmentByVideoTime(timeline.segments, videoTime);
            const audioTime = mapVideoToAudio(timeline.segments, videoTime, idx);

            // Only sync if audio position differs significantly
            if (Math.abs(audio.currentTime - audioTime) > 0.1) {
                audio.currentTime = audioTime;
                segmentIndexRef.current = idx;
                setCurrentSegmentIndex(idx);
            }

            // Update video playback rate immediately based on new segment
            const seg = timeline.segments[idx];
            video.playbackRate = clamp(seg.speed * userRateRef.current, 0.25, 4.0);
        };

        video.addEventListener("play", handleVideoPlay);
        video.addEventListener("pause", handleVideoPause);
        video.addEventListener("seeked", handleVideoSeeked);

        // Handle visibility change - restore playback when tab becomes visible
        // Chrome auto-pauses muted videos when tab is hidden, we need to resume
        const handleVisibilityChange = () => {
            if (!document.hidden && isActiveRef.current) {
                // Tab became visible, check if we need to restore playback
                // Audio continues playing in background, but video was paused by browser
                if (!audio.paused && video.paused) {
                    video.play().catch(() => {
                        // If video play fails, pause audio to keep sync
                        audio.pause();
                    });
                }
            }
        };

        document.addEventListener("visibilitychange", handleVisibilityChange);

        return () => {
            video.removeEventListener("play", handleVideoPlay);
            video.removeEventListener("pause", handleVideoPause);
            video.removeEventListener("seeked", handleVideoSeeked);
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [startTickLoop, stopTickLoop, isActive]);

    return {
        videoRef,
        audioRef,
        isActive,
        currentSegmentIndex,
        startSync,
        stopSync,
        seekToVideoTime,
        setUserRate,
        play,
        pause,
        getCurrentVideoTime,
    };
}
