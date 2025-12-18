"use client";

import { createContext, useContext, useRef, useState, useCallback, useMemo } from "react";
import type { VideoPlayerRef } from "@/components/video/VideoPlayer";

interface VideoPlayerContextValue {
    playerRef: React.RefObject<VideoPlayerRef | null>;
    currentTime: number;
    setCurrentTime: (time: number) => void;
    seekTo: (time: number) => void;
}

const VideoPlayerContext = createContext<VideoPlayerContextValue | null>(null);

interface VideoPlayerProviderProps {
    children: React.ReactNode;
}

export function VideoPlayerProvider({ children }: VideoPlayerProviderProps) {
    const playerRef = useRef<VideoPlayerRef | null>(null);
    const [currentTime, setCurrentTime] = useState(0);

    const seekTo = useCallback((time: number) => {
        playerRef.current?.seekTo(time);
    }, []);

    const value = useMemo(
        () => ({
            playerRef,
            currentTime,
            setCurrentTime,
            seekTo,
        }),
        [currentTime, seekTo]
    );

    return (
        <VideoPlayerContext.Provider value={value}>
            {children}
        </VideoPlayerContext.Provider>
    );
}

export function useVideoPlayer() {
    const context = useContext(VideoPlayerContext);
    if (!context) {
        throw new Error("useVideoPlayer must be used within a VideoPlayerProvider");
    }
    return context;
}

export function useVideoPlayerOptional() {
    return useContext(VideoPlayerContext);
}
