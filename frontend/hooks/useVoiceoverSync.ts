"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import type { SyncTimeline, SyncTimelineSegment } from "@/lib/api";

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
        if (segments[mid].dst_start <= audioTime) {
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
        if (segments[mid].src_start <= videoTime) {
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
    const rawVideoTime = seg.src_start + (audioTime - seg.dst_start) * seg.speed;
    // Clamp to segment boundaries to prevent overshoot
    const videoTime = clamp(rawVideoTime, seg.src_start, seg.src_end);
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
    const rawAudioTime = seg.dst_start + (videoTime - seg.src_start) / seg.speed;
    // Clamp to segment boundaries to prevent overshoot
    return clamp(rawAudioTime, seg.dst_start, seg.dst_end);
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
    // Flag to suppress ratechange handler when tick adjusts video.playbackRate
    const suppressRateChangeRef = useRef<boolean>(false);

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

        if (Math.abs(drift) > driftTolerance) {
            // Large drift: seek directly
            video.currentTime = videoTime;
            // Suppress ratechange handler to prevent feedback loop
            suppressRateChangeRef.current = true;
            video.playbackRate = clamp(targetRate, 0.25, 4.0);
            suppressRateChangeRef.current = false;
        } else {
            // Small drift: smooth rate adjustment
            const smoothedRate = lerp(video.playbackRate, targetRate, 0.6);
            // Suppress ratechange handler to prevent feedback loop
            suppressRateChangeRef.current = true;
            video.playbackRate = clamp(smoothedRate, 0.25, 4.0);
            suppressRateChangeRef.current = false;
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
            console.warn("useVoiceoverSync: video or audio ref not attached");
            return;
        }

        timelineRef.current = timeline;
        isActiveRef.current = true;
        setIsActive(true);

        // Mute video, audio will play the voiceover
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
                suppressRateChangeRef.current = true;
                video.playbackRate = clamp(seg.speed * userRateRef.current, 0.25, 4.0);
                suppressRateChangeRef.current = false;
            } else {
                segmentIndexRef.current = 0;
                setCurrentSegmentIndex(0);
            }

            // If video was playing, start audio too
            if (!video.paused) {
                audio.play().catch(() => {
                    console.warn("useVoiceoverSync: audio.play() blocked on startSync");
                });
            }

            startTickLoop();
        };

        // Wait for audio metadata before setting currentTime
        if (audio.readyState >= 1) {
            // Metadata already loaded
            setupSync();
        } else {
            // Wait for metadata
            const handleLoadedMetadata = () => {
                audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
                setupSync();
            };
            audio.addEventListener("loadedmetadata", handleLoadedMetadata);
        }
    }, [startTickLoop]);

    /**
     * Stop voiceover sync mode (restore original video)
     */
    const stopSync = useCallback(() => {
        const video = videoRef.current;
        const audio = audioRef.current;

        stopTickLoop();
        isActiveRef.current = false;
        timelineRef.current = null;
        setIsActive(false);

        if (video) {
            // Restore video
            video.muted = false;
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
        userRateRef.current = rate;
        const video = videoRef.current;
        const audio = audioRef.current;
        const timeline = timelineRef.current;

        if (isActiveRef.current && timeline && timeline.segments.length > 0) {
            // In sync mode: set audio rate to user rate, video rate = segment.speed * user rate
            if (audio) {
                audio.playbackRate = clamp(rate, 0.25, 4.0);
            }
            if (video) {
                const seg = timeline.segments[segmentIndexRef.current];
                suppressRateChangeRef.current = true;
                video.playbackRate = clamp(seg.speed * rate, 0.25, 4.0);
                suppressRateChangeRef.current = false;
            }
        } else if (video) {
            // Not in sync mode: just set video rate
            suppressRateChangeRef.current = true;
            video.playbackRate = clamp(rate, 0.25, 4.0);
            suppressRateChangeRef.current = false;
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
                    video.currentTime = lastSeg.src_end;
                }

                stopSync();
            }
        };

        audio.addEventListener("ended", handleAudioEnded);
        return () => audio.removeEventListener("ended", handleAudioEnded);
    }, [stopSync, isActive]);

    /**
     * Intercept native video controls.
     * When user interacts with native controls, mirror state to audio.
     * Re-run when isActive changes to ensure binding after audio element mounts.
     */
    useEffect(() => {
        const video = videoRef.current;
        const audio = audioRef.current;
        if (!video || !audio) return;

        // Mirror native video play to audio
        const handleVideoPlay = () => {
            if (isActiveRef.current && audio.paused) {
                audio.play().then(() => {
                    // Restart tick loop after successful audio play
                    startTickLoop();
                }).catch(() => {
                    // Autoplay blocked - user needs to interact first
                    console.warn("useVoiceoverSync: audio.play() blocked, pausing video");
                    video.pause();
                });
            } else if (isActiveRef.current && !audio.paused) {
                // Audio already playing, just restart tick loop
                startTickLoop();
            }
        };

        // Mirror native video pause to audio
        const handleVideoPause = () => {
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
            suppressRateChangeRef.current = true;
            video.playbackRate = clamp(seg.speed * userRateRef.current, 0.25, 4.0);
            suppressRateChangeRef.current = false;
        };

        // Mirror native video volume/mute changes to audio
        // In sync mode: video MUST stay muted, all volume controls affect audio only
        const handleVolumeChange = () => {
            if (!isActiveRef.current) return;

            // CRITICAL: Always force video to stay muted in sync mode
            // User clicking "unmute" on video controls must not unmute the video track
            if (!video.muted) {
                video.muted = true;
            }

            // Apply volume changes to audio (the actual sound source in sync mode)
            // User's volume slider on video controls affects voiceover audio
            audio.volume = video.volume;

            // If user sets volume to 0, also mute the audio
            // This gives user control over voiceover volume via native controls
            audio.muted = video.volume === 0;
        };

        // Mirror native video playback rate changes to sync system
        const handleRateChange = () => {
            if (!isActiveRef.current) return;
            // Ignore rate changes triggered by tick (not user-initiated)
            if (suppressRateChangeRef.current) return;
            const timeline = timelineRef.current;
            if (!timeline || !timeline.segments.length) return;

            // User changed playback rate via native controls
            // We need to extract the user's intended rate from the video's current rate
            // video.playbackRate = segment.speed * userRate, so userRate = video.playbackRate / segment.speed
            const seg = timeline.segments[segmentIndexRef.current];
            const newUserRate = video.playbackRate / seg.speed;
            const clampedUserRate = clamp(newUserRate, 0.25, 4.0);

            // Only update if significantly different to avoid feedback loops
            if (Math.abs(clampedUserRate - userRateRef.current) > 0.01) {
                userRateRef.current = clampedUserRate;
                audio.playbackRate = clampedUserRate;
            }
        };

        video.addEventListener("play", handleVideoPlay);
        video.addEventListener("pause", handleVideoPause);
        video.addEventListener("seeked", handleVideoSeeked);
        video.addEventListener("volumechange", handleVolumeChange);
        video.addEventListener("ratechange", handleRateChange);

        return () => {
            video.removeEventListener("play", handleVideoPlay);
            video.removeEventListener("pause", handleVideoPause);
            video.removeEventListener("seeked", handleVideoSeeked);
            video.removeEventListener("volumechange", handleVolumeChange);
            video.removeEventListener("ratechange", handleRateChange);
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
