"use client";

import { createContext, useContext, useMemo } from "react";
import { useSubtitleManagement, type SubtitleMode, type UseSubtitleManagementReturn } from "@/hooks/useSubtitleManagement";
import type { ContentItem } from "@/lib/api";

type SubtitleContextValue = UseSubtitleManagementReturn;

const SubtitleContext = createContext<SubtitleContextValue | null>(null);

interface SubtitleProviderProps {
    videoId: string;
    content: ContentItem | null;
    children: React.ReactNode;
}

export function SubtitleProvider({ videoId, content, children }: SubtitleProviderProps) {
    const subtitleManagement = useSubtitleManagement({ videoId, content });

    const value = useMemo(() => subtitleManagement, [subtitleManagement]);

    return (
        <SubtitleContext.Provider value={value}>
            {children}
        </SubtitleContext.Provider>
    );
}

export function useSubtitles() {
    const context = useContext(SubtitleContext);
    if (!context) {
        throw new Error("useSubtitles must be used within a SubtitleProvider");
    }
    return context;
}

export function useSubtitlesOptional() {
    return useContext(SubtitleContext);
}

export type { SubtitleMode };
