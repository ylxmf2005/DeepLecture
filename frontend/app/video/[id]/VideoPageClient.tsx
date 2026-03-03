"use client";

import { useEffect, useRef, useCallback, useMemo, useId, useState } from "react";
import dynamic from "next/dynamic";
import { VideoPlayerRef } from "@/components/video/VideoPlayer";
import type { ContentItem, VoiceoverEntry } from "@/lib/api";
import { createBookmark } from "@/lib/api/bookmarks";
import { getActiveSubtitles } from "@/lib/subtitleSearch";
import { formatTime } from "@/lib/timeFormat";
import { toast } from "sonner";
import { useVideoPageState } from "@/hooks/useVideoPageState";
import { useSmartSkip } from "@/hooks/useSmartSkip";
import { useSubtitleRepeat } from "@/hooks/useSubtitleRepeat";
import { useVideoPageHandlers } from "@/hooks/useVideoPageHandlers";
import { useSubtitleManagement } from "@/hooks/useSubtitleManagement";
import { SubtitleDisplayMode } from "@/stores/types";
import { useVideoProgress, RESUME_TOLERANCE_SECONDS } from "@/hooks/useVideoProgress";
import { useThrottledTimeUpdate } from "@/hooks/useThrottledTimeUpdate";
import { useNoteGeneration } from "@/hooks/useNoteGeneration";
import { useDndTabLayout } from "@/hooks/useDndTabLayout";
import { useLive2DAudioSync } from "@/hooks/useLive2DAudioSync";
import { Settings, Wand2, Loader2 } from "lucide-react";
import { DndContext, DragOverlay } from "@dnd-kit/core";
import { VideoConfigProvider } from "@/contexts/VideoConfigContext";

// Lazy load dialogs - only loaded when opened
const ActionsDialog = dynamic(
    () => import("@/components/dialogs/ActionsDialog").then((mod) => mod.ActionsDialog),
    { ssr: false }
);
const SettingsDialog = dynamic(
    () => import("@/components/dialogs/SettingsDialog").then((mod) => mod.SettingsDialog),
    { ssr: false }
);
const Live2DCanvas = dynamic(() => import("@/components/live2d/Live2DCanvas"), { ssr: false });
import { useLearnerProfile } from "@/components/providers/LearnerProfileProvider";
import { useConfirmDialog } from "@/contexts/ConfirmDialogContext";
import { VideoPlayerSection, NotesPanel, SidebarTabs } from "@/components/video";
import { HeaderActionPortal } from "@/components/layout/HeaderActionPortal";
import { FocusModeHandler } from "@/components/features/FocusModeHandler";
import { ErrorBoundary, logger } from "@/shared/infrastructure";

const log = logger.scope("VideoPage");
import {
    useSidebarSubtitleMode as useSidebarSubtitleModeStore,
    useVideoDeck,
    useSmartSkipEnabled,
    useVideoStateStore,
    useQuickToggleOriginalVoiceoverId,
    useQuickToggleTranslatedVoiceoverId,
} from "@/stores";
import { useVideoPageSettings } from "@/hooks/useVideoPageSettings";
import { TAB_CONFIG } from "@/components/dnd/DraggableTabBar";
import { getResumeCandidate } from "@/lib/videoResume";
import { applyResumeSeek } from "@/lib/videoResumeSeek";

export { type ProcessingAction } from "@/hooks/useVideoPageState";

const SIDEBAR_SUBTITLE_MODE_KEY_PREFIX = "courseSubtitle:subtitle-mode:sidebar";
const buildSidebarSubtitleModeKey = (videoId: string) => `${SIDEBAR_SUBTITLE_MODE_KEY_PREFIX}:${videoId}`;

export interface VideoPageClientProps {
    videoId: string;
    initialContent: ContentItem | null;
    initialVoiceovers: VoiceoverEntry[];
}

export default function VideoPageClient({ videoId, initialContent, initialVoiceovers }: VideoPageClientProps) {
    const dndContextId = useId();
    // Learner profile
    const { profile: learnerProfile } = useLearnerProfile();
    const { confirm } = useConfirmDialog();

    // Global settings from optimized hook (uses useShallow internally)
    const { settings, actions: settingsActions } = useVideoPageSettings();
    const { playback, language, hideSidebars, viewMode, live2d } = settings;
    const { toggleLive2d, setLive2dModelPosition, setLive2dModelScale, setViewMode } = settingsActions;

    // Derived values for convenience (used by FocusModeHandler, handlers, etc.)
    const autoPauseOnLeave = playback.autoPauseOnLeave;
    const autoResumeOnReturn = playback.autoResumeOnReturn;
    const autoSwitchSubtitlesOnLeave = playback.autoSwitchSubtitlesOnLeave;
    const autoSwitchVoiceoverOnLeave = playback.autoSwitchVoiceoverOnLeave;
    const voiceoverAutoSwitchThresholdMs = playback.voiceoverAutoSwitchThresholdMs;
    const summaryThresholdSeconds = playback.summaryThresholdSeconds;
    const subtitleContextWindowSeconds = playback.subtitleContextWindowSeconds;
    const subtitleRepeatCount = playback.subtitleRepeatCount;
    const originalLanguage = language.original;
    /** Target language for all AI outputs (translations, explanations, timelines, notes) */
    const targetLanguage = language.translated;
    const live2dEnabled = live2d.enabled;
    const live2dModelPath = live2d.modelPath;
    const live2dModelPosition = live2d.modelPosition;
    const live2dModelScale = live2d.modelScale;
    const live2dSyncWithVideoAudio = live2d.syncWithVideoAudio;

    // Core page state
    const pageState = useVideoPageState({ videoId, originalLanguage, targetLanguage, learnerProfile, initialContent, initialVoiceovers });
    const {
        content,
        loading,
        processing,
        setProcessing,
        processingAction,
        setProcessingAction,
        generatingVideo,
        voiceoverProcessing,
        setVoiceoverProcessing,
        voiceoverName,
        setVoiceoverName,
        voiceovers,
        setVoiceovers,
        voiceoversLoading,
        selectedVoiceoverId,
        setSelectedVoiceoverId,
        selectedVoiceoverSyncTimeline,
        timelineEntries,
        setTimelineEntries,
        timelineLoading,
        setTimelineLoading,
        currentTime,
        setCurrentTime,
        refreshExplanations,
        setRefreshExplanations,
        refreshVerification,
        refreshCheatsheet,
        refreshQuiz,
        refreshFlashcard,
        subtitleRefreshVersion,
        askContext,
        setAskContext,
        isSettingsOpen,
        setIsSettingsOpen,
        isActionsOpen,
        setIsActionsOpen,
        generatingNote,
        setGeneratingNote,
    } = pageState;

    // Store hooks
    const skipRamblingEnabled = useSmartSkipEnabled(videoId);
    const deck = useVideoDeck(videoId);
    const setSubtitleModeSidebarStore = useVideoStateStore((store) => store.setSubtitleModeSidebar);
    const setDeckStore = useVideoStateStore((store) => store.setDeck);
    const setSmartSkipEnabledStore = useVideoStateStore((store) => store.setSmartSkipEnabled);
    const persistedProgress = useVideoStateStore((store) => store.videos[videoId]?.progressSeconds ?? null);
    const quickToggleOriginalVoiceoverId = useQuickToggleOriginalVoiceoverId(videoId);
    const quickToggleTranslatedVoiceoverId = useQuickToggleTranslatedVoiceoverId(videoId);
    const setQuickToggleOriginalVoiceoverIdStore = useVideoStateStore((store) => store.setQuickToggleOriginalVoiceoverId);
    const setQuickToggleTranslatedVoiceoverIdStore = useVideoStateStore((store) => store.setQuickToggleTranslatedVoiceoverId);

    // DnD tab layout (extracted hook)
    const {
        activeId,
        sensors,
        collisionDetection,
        handleDragStart,
        handleDragOver,
        handleDragEnd,
        handleDragCancel,
    } = useDndTabLayout();

    // Subtitle management - uses semantic mode names (source/target/dual/dual_reversed)
    const {
        subtitlesSource,
        subtitlesTarget,
        subtitlesDual,
        subtitlesDualReversed,
        subtitlesLoading,
        subtitleMode: playerSubtitleMode,
        setSubtitleMode: setPlayerSubtitleMode,
        currentSubtitles: playerSubtitles,
    } = useSubtitleManagement({ videoId, content, originalLanguage, targetLanguage, subtitleRefreshVersion });

    const sidebarSubtitleMode = useSidebarSubtitleModeStore(videoId);

    // Compute sidebar subtitles based on semantic mode
    const sidebarSubtitles = useMemo(() => {
        if (sidebarSubtitleMode === "dual" && subtitlesDual.length > 0) return subtitlesDual;
        if (sidebarSubtitleMode === "dual_reversed" && subtitlesDualReversed.length > 0) return subtitlesDualReversed;
        if (sidebarSubtitleMode === "target" && subtitlesTarget.length > 0) return subtitlesTarget;
        return subtitlesSource;
    }, [sidebarSubtitleMode, subtitlesSource, subtitlesTarget, subtitlesDual, subtitlesDualReversed]);

    // Callback for setting sidebar subtitle mode
    const handleSetSidebarSubtitleMode = useCallback(
        (mode: SubtitleDisplayMode) => setSubtitleModeSidebarStore(videoId, mode),
        [setSubtitleModeSidebarStore, videoId]
    );

    // Refs
    const playerRef = useRef<VideoPlayerRef>(null);
    const hydrationResumeHandledForVideoRef = useRef<string | null>(null);
    const readyVideoElementRef = useRef<HTMLVideoElement | null>(null);
    const persistedProgressRef = useRef<number | null>(null);
    const resumeTickTimerRef = useRef<number | null>(null);

    // Live2D audio sync (extracted hook)
    const { live2dRef, connectLive2DAudio, onLive2DLoad } = useLive2DAudioSync({
        playerRef,
        live2dEnabled,
        live2dSyncWithVideoAudio,
        live2dModelPath,
        selectedVoiceoverId,
    });

    // Note generation (extracted hook)
    const { noteEditorRef, handleNoteEditorReady, handleGenerateNote } = useNoteGeneration({
        videoId,
        targetLanguage,
        learnerProfile,
        generatingNote,
        setGeneratingNote,
        confirm,
    });

    // Video progress persistence
    const {
        resumeTargetRef,
        lastPersistedProgressRef,
        maybePersistProgress,
    } = useVideoProgress({ videoId, playerRef });

    useEffect(() => {
        persistedProgressRef.current = persistedProgress;
    }, [persistedProgress]);

    useEffect(() => {
        hydrationResumeHandledForVideoRef.current = null;
        readyVideoElementRef.current = null;
        if (resumeTickTimerRef.current !== null) {
            window.clearInterval(resumeTickTimerRef.current);
            resumeTickTimerRef.current = null;
        }
    }, [videoId]);

    useEffect(() => {
        return () => {
            if (resumeTickTimerRef.current !== null) {
                window.clearInterval(resumeTickTimerRef.current);
                resumeTickTimerRef.current = null;
            }
        };
    }, []);

    // Fullscreen should never be sticky across refresh.
    // During reload boot, repeatedly enforce exitFullscreen in case browser restores it asynchronously.
    useEffect(() => {
        if (typeof window === "undefined" || typeof document === "undefined") return;

        const navEntry = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
        const legacyNavigation = (performance as Performance & { navigation?: { type?: number } }).navigation;
        const isReload = navEntry?.type === "reload" || legacyNavigation?.type === 1;
        if (!isReload) return;

        const enforceNoFullscreen = async () => {
            if (document.fullscreenElement) {
                try {
                    await document.exitFullscreen();
                } catch (error) {
                    log.warn("Failed to exit fullscreen during reload guard", {
                        error: error instanceof Error ? error.message : String(error),
                    });
                }
            }
        };

        const handleFullscreenChange = () => {
            void enforceNoFullscreen();
        };
        document.addEventListener("fullscreenchange", handleFullscreenChange);

        void enforceNoFullscreen();
        const intervalId = window.setInterval(() => {
            void enforceNoFullscreen();
        }, 200);
        const timeoutId = window.setTimeout(() => {
            window.clearInterval(intervalId);
            document.removeEventListener("fullscreenchange", handleFullscreenChange);
        }, 2500);

        return () => {
            window.clearInterval(intervalId);
            window.clearTimeout(timeoutId);
            document.removeEventListener("fullscreenchange", handleFullscreenChange);
        };
    }, [videoId]);

    // Transient fullscreen view modes must never survive navigation/hydration.
    // Only run on mount — the store's sanitizeHydratedViewMode handles the persistence case.
    useEffect(() => {
        if (viewMode === "web-fullscreen" || viewMode === "fullscreen") {
            setViewMode("normal");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Smart Skip hook
    const { handleSmartSkipCheck, handleSeek } = useSmartSkip({
        playerRef,
        skipRamblingEnabled,
        timelineEntries,
        setCurrentTime,
    });

    // Throttled time update
    const baseHandleTimeUpdate = useThrottledTimeUpdate({
        onTimeChange: setCurrentTime,
        onSmartSkipCheck: handleSmartSkipCheck,
        onPersistProgress: maybePersistProgress,
    });

    // Subtitle repeat hook
    const { handleTimeUpdate, resetRepeatState } = useSubtitleRepeat({
        playerRef,
        subtitles: playerSubtitles,
        subtitleRepeatCount,
        onBaseTimeUpdate: baseHandleTimeUpdate,
    });

    // Bookmark timestamps for progress bar markers (set by BookmarkTab via onBookmarksChange)
    const [bookmarkTimestamps, setBookmarkTimestamps] = useState<number[]>([]);
    const [refreshBookmarks, setRefreshBookmarks] = useState(0);

    // Handle B-key bookmark creation
    const handleAddBookmark = useCallback(async (time: number) => {
        try {
            const active = getActiveSubtitles(subtitlesSource, time);
            const title = active.map((s) => s.text).join(" ").trim() || `Bookmark at ${formatTime(time)}`;
            const item = await createBookmark(videoId, time, title);
            setBookmarkTimestamps((prev) => [...prev, item.timestamp].sort((a, b) => a - b));
            setRefreshBookmarks((prev) => prev + 1);
            toast.success("Bookmark added");
        } catch {
            toast.error("Failed to add bookmark");
        }
    }, [videoId, subtitlesSource]);

    // Event handlers
    const handlers = useVideoPageHandlers({
        videoId,
        originalLanguage,
        targetLanguage,
        learnerProfile,
        subtitleContextWindowSeconds,
        subtitlesSource,
        playerSubtitles,
        voiceoverName,
        noteEditorRef,
        setProcessing,
        setProcessingAction,
        setRefreshExplanations,
        setVoiceoverProcessing,
        setVoiceovers,
        selectedVoiceoverId,
        setSelectedVoiceoverId,
        setTimelineLoading,
        setTimelineEntries,
        setAskContext,
        setDeckStore,
        hasSubtitles: content?.subtitleStatus === "ready",
        hasEnhancedSubtitles: content?.enhancedStatus === "ready",
    });

    // Migrate localStorage to store (handles legacy values)
    useEffect(() => {
        if (typeof window === "undefined" || !videoId) return;

        // Migrate legacy sidebar subtitle mode: en→source, zh→target, en_zh→dual, zh_en→dual_reversed
        const sidebarKey = buildSidebarSubtitleModeKey(videoId);
        const storedSidebar = window.localStorage.getItem(sidebarKey);
        if (storedSidebar) {
            const legacyMap: Record<string, SubtitleDisplayMode> = {
                en: "source",
                zh: "target",
                en_zh: "dual",
                zh_en: "dual_reversed",
                // Also support new semantic values for forward compatibility
                source: "source",
                target: "target",
                dual: "dual",
                dual_reversed: "dual_reversed",
            };
            const mapped = legacyMap[storedSidebar];
            if (mapped) {
                setSubtitleModeSidebarStore(videoId, mapped);
            }
            window.localStorage.removeItem(sidebarKey);
        }

        const deckKey = `courseSubtitle:video-deck:${videoId}`;
        const rawDeck = window.localStorage.getItem(deckKey);
        if (rawDeck) {
            try {
                const parsed = JSON.parse(rawDeck) as unknown;
                if (parsed && typeof parsed === "object" && "id" in parsed && "name" in parsed) {
                    const deck = parsed as { id: string; name: string };
                    if (typeof deck.id === "string" && typeof deck.name === "string") {
                        setDeckStore(videoId, deck);
                    }
                }
            } catch {
                // Corrupted localStorage data - silently ignore and remove
            }
            window.localStorage.removeItem(deckKey);
        }
    }, [videoId, setSubtitleModeSidebarStore, setDeckStore]);

    // Reset repeat state when video/subtitles change
    useEffect(() => {
        resetRepeatState();
    }, [videoId, selectedVoiceoverId, playerSubtitles, resetRepeatState]);

    // Reset Smart Skip when learner profile intentionally changes (not on hydration)
    const prevLearnerProfileRef = useRef<string | null>(null);
    useEffect(() => {
        // On first mount or hydration, just record the value without resetting
        if (prevLearnerProfileRef.current === null) {
            prevLearnerProfileRef.current = learnerProfile;
            return;
        }
        // Only reset if the profile actually changed from its previous value
        if (prevLearnerProfileRef.current !== learnerProfile && videoId) {
            setSmartSkipEnabledStore(videoId, false);
        }
        prevLearnerProfileRef.current = learnerProfile;
    }, [learnerProfile, videoId, setSmartSkipEnabledStore]);

    const attemptResumeFromSavedProgress = useCallback(
        (videoElement: HTMLVideoElement): boolean => {
            if (hydrationResumeHandledForVideoRef.current === videoId) return true;

            const candidate = getResumeCandidate({
                resumeTarget: resumeTargetRef.current,
                persistedProgress: persistedProgressRef.current,
            });
            if (candidate === null || candidate <= 0) return false;

            const clampTarget = (target: number) => {
                const duration = videoElement.duration;
                if (!Number.isFinite(duration) || duration <= 0) return Math.max(0, target);
                const maxPlayable = Math.max(duration - RESUME_TOLERANCE_SECONDS, 0);
                return Math.min(Math.max(target, 0), maxPlayable);
            };

            const safeTarget = clampTarget(candidate);
            resumeTargetRef.current = safeTarget;

            if (videoElement.readyState < 1) return false;

            try {
                // Use player API first (sync-aware), then helper guarantees a direct video fallback.
                applyResumeSeek(safeTarget, playerRef.current, videoElement);
            } catch (error) {
                log.warn("Failed to apply saved progress", { error: error instanceof Error ? error.message : String(error) });
                return false;
            }

            const observedTime = playerRef.current?.getCurrentTime() ?? videoElement.currentTime;
            const delta = Math.abs(observedTime - safeTarget);
            if (delta > RESUME_TOLERANCE_SECONDS) return false;

            hydrationResumeHandledForVideoRef.current = videoId;
            resumeTargetRef.current = null;
            lastPersistedProgressRef.current = observedTime;
            setCurrentTime(observedTime);
            return true;
        },
        [videoId, lastPersistedProgressRef, resumeTargetRef, setCurrentTime]
    );

    // Player ready handler
    const handlePlayerReady = useCallback(
        (videoElement: HTMLVideoElement) => {
            readyVideoElementRef.current = videoElement;

            // Connect Live2D audio sync (handled by extracted hook)
            connectLive2DAudio(videoElement);

            attemptResumeFromSavedProgress(videoElement);
        },
        [connectLive2DAudio, attemptResumeFromSavedProgress]
    );

    const isVideoReadyForResume = !loading && !!content;

    // Keep trying resume for a short window once page/player is ready.
    // This removes dependency on manual actions (for example voiceover switching).
    useEffect(() => {
        if (!isVideoReadyForResume) return;
        if (hydrationResumeHandledForVideoRef.current === videoId) return;

        const candidate = getResumeCandidate({
            resumeTarget: resumeTargetRef.current,
            persistedProgress,
        });
        if (candidate === null) return;

        let elapsedMs = 0;
        const MAX_MS = 20000;
        const INTERVAL_MS = 200;

        const clearTickTimer = () => {
            if (resumeTickTimerRef.current !== null) {
                window.clearInterval(resumeTickTimerRef.current);
                resumeTickTimerRef.current = null;
            }
        };

        const tick = () => {
            const videoElement = readyVideoElementRef.current ?? playerRef.current?.getVideoElement();
            if (!videoElement) return;
            attemptResumeFromSavedProgress(videoElement);
        };

        tick();

        clearTickTimer();
        resumeTickTimerRef.current = window.setInterval(() => {
            if (hydrationResumeHandledForVideoRef.current === videoId) {
                clearTickTimer();
                return;
            }

            elapsedMs += INTERVAL_MS;
            if (elapsedMs >= MAX_MS) {
                clearTickTimer();
                return;
            }

            tick();
        }, INTERVAL_MS);

        const videoElement = readyVideoElementRef.current ?? playerRef.current?.getVideoElement();
        if (!videoElement) {
            return () => {
                clearTickTimer();
            };
        }

        const handleMediaReady = () => {
            tick();
        };

        videoElement.addEventListener("loadedmetadata", handleMediaReady);
        videoElement.addEventListener("loadeddata", handleMediaReady);
        videoElement.addEventListener("canplay", handleMediaReady);
        videoElement.addEventListener("seeked", handleMediaReady);

        return () => {
            clearTickTimer();
            videoElement.removeEventListener("loadedmetadata", handleMediaReady);
            videoElement.removeEventListener("loadeddata", handleMediaReady);
            videoElement.removeEventListener("canplay", handleMediaReady);
            videoElement.removeEventListener("seeked", handleMediaReady);
        };
    }, [
        isVideoReadyForResume,
        videoId,
        persistedProgress,
        selectedVoiceoverId,
        selectedVoiceoverSyncTimeline,
        attemptResumeFromSavedProgress,
        resumeTargetRef,
    ]);

    // Handle ESC key to exit web-fullscreen mode
    useEffect(() => {
        if (viewMode !== "web-fullscreen") return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                setViewMode("normal");
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [viewMode, setViewMode]);

    // Header action buttons — rendered unconditionally so they appear even during loading
    const headerActions = (
        <HeaderActionPortal>
            <button
                onClick={() => setIsActionsOpen(true)}
                className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                title="Actions"
                disabled={loading || !content}
            >
                <Wand2 className="w-5 h-5" />
            </button>
            <button
                onClick={() => setIsSettingsOpen(true)}
                className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                title="Video Configuration"
                disabled={loading || !content}
            >
                <Settings className="w-5 h-5" />
            </button>
        </HeaderActionPortal>
    );

    // Loading state
    if (loading) {
        return (
            <>
                {headerActions}
                <div className="flex h-[50vh] items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
                </div>
            </>
        );
    }

    // Not found state
    if (!content) {
        return (
            <>
                {headerActions}
                <div className="text-center py-12">
                    <h2 className="text-xl font-semibold">Content not found</h2>
                </div>
            </>
        );
    }

    const formattedCreatedDate = new Intl.DateTimeFormat("en-US", {
        timeZone: "UTC",
        year: "numeric",
        month: "short",
        day: "numeric",
    }).format(new Date(content.createdAt));

    return (
        <VideoConfigProvider contentId={videoId}>
        <DndContext
            id={dndContextId}
            sensors={sensors}
            collisionDetection={collisionDetection}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
            onDragCancel={handleDragCancel}
        >
            <div className={`grid ${
                viewMode === "web-fullscreen"
                    ? "fixed inset-0 z-50 h-screen w-screen bg-black p-0 gap-0 grid-cols-1"
                    : `gap-6 h-[130vh] ${
                        hideSidebars
                            ? "grid-cols-1"
                            : viewMode === "widescreen"
                                ? "grid-cols-1"
                                : "grid-cols-1 md:grid-cols-3"
                    }`
            }`}>
                {/* Video Player Column - full width in widescreen mode */}
                <div className={`flex flex-col ${
                    viewMode === "web-fullscreen"
                        ? "h-full min-h-0 gap-0 col-span-1"
                        : `gap-4 ${
                            viewMode === "widescreen"
                                ? "col-span-1"
                                : hideSidebars
                                    ? "col-span-1"
                                    : "md:col-span-2"
                        } ${viewMode === "widescreen" ? "" : "h-full min-h-0"}`
                }`}>
                    {/* Video Title and Metadata */}
                    {viewMode !== "web-fullscreen" && (
                        <div className="flex items-baseline justify-between gap-4">
                            <h1 className="text-xl font-semibold truncate">{content.filename}</h1>
                            <span className="text-sm text-muted-foreground whitespace-nowrap">
                                {formattedCreatedDate}
                            </span>
                        </div>
                    )}
                    <ErrorBoundary
                        component="VideoPlayerSection"
                        fallback={(error, reset) => (
                            <div className="flex flex-col items-center justify-center p-8 bg-muted/50 rounded-lg">
                                <p className="text-destructive mb-4">Video player error: {error.message}</p>
                                <button onClick={reset} className="px-4 py-2 bg-primary text-primary-foreground rounded-md">
                                    Reload Player
                                </button>
                            </div>
                        )}
                    >
                        <VideoPlayerSection
                            ref={playerRef}
                            content={content}
                            videoId={videoId}
                            selectedVoiceoverId={selectedVoiceoverId}
                            selectedVoiceoverSyncTimeline={selectedVoiceoverSyncTimeline}
                            playerSubtitles={playerSubtitles}
                            playerSubtitleMode={playerSubtitleMode}
                            setPlayerSubtitleMode={setPlayerSubtitleMode}
                            hasTranslation={content.enhancedStatus === "ready"}
                            quickToggleOriginalVoiceoverId={quickToggleOriginalVoiceoverId}
                            quickToggleTranslatedVoiceoverId={quickToggleTranslatedVoiceoverId}
                            onVoiceoverChange={setSelectedVoiceoverId}
                            generatingVideo={generatingVideo}
                            onTimeUpdate={handleTimeUpdate}
                            onCapture={handlers.handleCapture}
                            onAskAtTime={handlers.handleAskAtTime}
                            onAddNoteAtTime={handlers.handleAddNoteAtTime}
                            onPlayerReady={handlePlayerReady}
                            onGenerateSlideLecture={handlers.handleGenerateSlideLecture}
                            slideDeck={deck}
                            onUploadSlide={handlers.handleUploadSlide}
                            viewMode={viewMode}
                            onViewModeChange={setViewMode}
                            bookmarkTimestamps={bookmarkTimestamps}
                            onAddBookmark={handleAddBookmark}
                            className={viewMode === "web-fullscreen" ? "w-full h-full" : undefined}
                        />
                    </ErrorBoundary>

                    {/* NotesPanel in normal mode (not widescreen) */}
                    {!hideSidebars && viewMode !== "widescreen" && viewMode !== "web-fullscreen" && (
                        <NotesPanel
                            videoId={videoId}
                            onEditorReady={handleNoteEditorReady}
                            content={content}
                            currentTime={currentTime}
                            sidebarSubtitleMode={sidebarSubtitleMode}
                            setSidebarSubtitleMode={handleSetSidebarSubtitleMode}
                            sidebarSubtitles={sidebarSubtitles}
                            subtitlesSource={subtitlesSource}
                            subtitlesTarget={subtitlesTarget}
                            subtitlesDual={subtitlesDual}
                            subtitlesDualReversed={subtitlesDualReversed}
                            subtitlesLoading={subtitlesLoading}
                            originalLanguage={originalLanguage}
                            processing={processing}
                            processingAction={processingAction}
                            timelineEntries={timelineEntries}
                            timelineLoading={timelineLoading}
                            refreshExplanations={refreshExplanations}
                            refreshVerification={refreshVerification}
                            refreshCheatsheet={refreshCheatsheet}
                            refreshBookmarks={refreshBookmarks}
                            refreshQuiz={refreshQuiz}
                            refreshFlashcard={refreshFlashcard}
                            askContext={askContext}
                            learnerProfile={learnerProfile}
                            subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                            onSeek={handleSeek}
                            onAddToAsk={handlers.handleAddToAsk}
                            onAddToNotes={handlers.handleAddToNotes}
                            onRemoveFromAsk={handlers.handleRemoveFromAsk}
                            onGenerateSubtitles={handlers.handleGenerateSubtitles}
                            onGenerateTimeline={handlers.handleGenerateTimeline}
                            onBookmarksChange={setBookmarkTimestamps}
                        />
                    )}
                </div>

                {/* Sidebar in normal mode (not widescreen) */}
                {!hideSidebars && viewMode !== "widescreen" && viewMode !== "web-fullscreen" && (
                    <SidebarTabs
                        content={content}
                        videoId={videoId}
                        currentTime={currentTime}
                        sidebarSubtitleMode={sidebarSubtitleMode}
                        setSidebarSubtitleMode={handleSetSidebarSubtitleMode}
                        sidebarSubtitles={sidebarSubtitles}
                        subtitlesSource={subtitlesSource}
                        subtitlesTarget={subtitlesTarget}
                        subtitlesDual={subtitlesDual}
                        subtitlesDualReversed={subtitlesDualReversed}
                        subtitlesLoading={subtitlesLoading}
                        originalLanguage={originalLanguage}
                        processing={processing}
                        processingAction={processingAction}
                        timelineEntries={timelineEntries}
                        timelineLoading={timelineLoading}
                        refreshExplanations={refreshExplanations}
                        refreshVerification={refreshVerification}
                        refreshCheatsheet={refreshCheatsheet}
                        refreshBookmarks={refreshBookmarks}
                        refreshQuiz={refreshQuiz}
                        refreshFlashcard={refreshFlashcard}
                        askContext={askContext}
                        learnerProfile={learnerProfile}
                        subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                        onSeek={handleSeek}
                        onAddToAsk={handlers.handleAddToAsk}
                        onAddToNotes={handlers.handleAddToNotes}
                        onRemoveFromAsk={handlers.handleRemoveFromAsk}
                        onGenerateSubtitles={handlers.handleGenerateSubtitles}
                        onGenerateTimeline={handlers.handleGenerateTimeline}
                        onBookmarksChange={setBookmarkTimestamps}
                    />
                )}

                {/* Widescreen mode: NotesPanel and Sidebar side by side below video */}
                {!hideSidebars && viewMode === "widescreen" && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 min-h-[50vh] max-h-[80vh]">
                        <NotesPanel
                            videoId={videoId}
                            onEditorReady={handleNoteEditorReady}
                            content={content}
                            currentTime={currentTime}
                            sidebarSubtitleMode={sidebarSubtitleMode}
                            setSidebarSubtitleMode={handleSetSidebarSubtitleMode}
                            sidebarSubtitles={sidebarSubtitles}
                            subtitlesSource={subtitlesSource}
                            subtitlesTarget={subtitlesTarget}
                            subtitlesDual={subtitlesDual}
                            subtitlesDualReversed={subtitlesDualReversed}
                            subtitlesLoading={subtitlesLoading}
                            originalLanguage={originalLanguage}
                            processing={processing}
                            processingAction={processingAction}
                            timelineEntries={timelineEntries}
                            timelineLoading={timelineLoading}
                            refreshExplanations={refreshExplanations}
                            refreshVerification={refreshVerification}
                            refreshCheatsheet={refreshCheatsheet}
                            refreshBookmarks={refreshBookmarks}
                            refreshQuiz={refreshQuiz}
                            refreshFlashcard={refreshFlashcard}
                            askContext={askContext}
                            learnerProfile={learnerProfile}
                            subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                            onSeek={handleSeek}
                            onAddToAsk={handlers.handleAddToAsk}
                            onAddToNotes={handlers.handleAddToNotes}
                            onRemoveFromAsk={handlers.handleRemoveFromAsk}
                            onGenerateSubtitles={handlers.handleGenerateSubtitles}
                            onGenerateTimeline={handlers.handleGenerateTimeline}
                            onBookmarksChange={setBookmarkTimestamps}
                        />
                        <SidebarTabs
                            content={content}
                            videoId={videoId}
                            currentTime={currentTime}
                            sidebarSubtitleMode={sidebarSubtitleMode}
                            setSidebarSubtitleMode={handleSetSidebarSubtitleMode}
                            sidebarSubtitles={sidebarSubtitles}
                            subtitlesSource={subtitlesSource}
                            subtitlesTarget={subtitlesTarget}
                            subtitlesDual={subtitlesDual}
                            subtitlesDualReversed={subtitlesDualReversed}
                            subtitlesLoading={subtitlesLoading}
                            originalLanguage={originalLanguage}
                            processing={processing}
                            processingAction={processingAction}
                            timelineEntries={timelineEntries}
                            timelineLoading={timelineLoading}
                            refreshExplanations={refreshExplanations}
                            refreshVerification={refreshVerification}
                            refreshCheatsheet={refreshCheatsheet}
                            refreshBookmarks={refreshBookmarks}
                            refreshQuiz={refreshQuiz}
                            refreshFlashcard={refreshFlashcard}
                            askContext={askContext}
                            learnerProfile={learnerProfile}
                            subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                            onSeek={handleSeek}
                            onAddToAsk={handlers.handleAddToAsk}
                            onAddToNotes={handlers.handleAddToNotes}
                            onRemoveFromAsk={handlers.handleRemoveFromAsk}
                            onGenerateSubtitles={handlers.handleGenerateSubtitles}
                            onGenerateTimeline={handlers.handleGenerateTimeline}
                            onBookmarksChange={setBookmarkTimestamps}
                        />
                    </div>
                )}

            <SettingsDialog
                isOpen={isSettingsOpen}
                onClose={() => setIsSettingsOpen(false)}
                video={content}
                initialScope="video"
            />

            <ActionsDialog
                isOpen={isActionsOpen}
                onClose={() => setIsActionsOpen(false)}
                video={content}
                processing={processing}
                processingAction={processingAction}
                handleGenerateSubtitles={handlers.handleGenerateSubtitles}
                handleTranslateSubtitles={handlers.handleTranslateSubtitles}
                voiceoverName={voiceoverName}
                setVoiceoverName={setVoiceoverName}
                voiceoverProcessing={voiceoverProcessing}
                handleGenerateVoiceover={handlers.handleGenerateVoiceover}
                selectedVoiceoverId={selectedVoiceoverId}
                setSelectedVoiceoverId={setSelectedVoiceoverId}
                voiceovers={voiceovers}
                voiceoversLoading={voiceoversLoading}
                handleDeleteVoiceover={handlers.handleDeleteVoiceover}
                handleUpdateVoiceover={handlers.handleUpdateVoiceover}
                quickToggleOriginalVoiceoverId={quickToggleOriginalVoiceoverId}
                setQuickToggleOriginalVoiceoverId={(id) => setQuickToggleOriginalVoiceoverIdStore(videoId, id)}
                quickToggleTranslatedVoiceoverId={quickToggleTranslatedVoiceoverId}
                setQuickToggleTranslatedVoiceoverId={(id) => setQuickToggleTranslatedVoiceoverIdStore(videoId, id)}
                timelineLoading={timelineLoading}
                hasTimeline={timelineEntries.length > 0}
                handleGenerateTimeline={handlers.handleGenerateTimeline}
                generatingVideo={generatingVideo}
                handleGenerateSlideLecture={handlers.handleGenerateSlideLecture}
                handleGenerateNote={handleGenerateNote}
                generatingNote={generatingNote}
            />

            <FocusModeHandler
                playerRef={playerRef}
                subtitles={playerSubtitles}
                learnerProfile={learnerProfile}
                autoPauseOnLeave={autoPauseOnLeave}
                autoResumeOnReturn={autoResumeOnReturn}
                autoSwitchSubtitlesOnLeave={autoSwitchSubtitlesOnLeave}
                autoSwitchVoiceoverOnLeave={autoSwitchVoiceoverOnLeave}
                voiceoverAutoSwitchThresholdMs={voiceoverAutoSwitchThresholdMs}
                subtitleMode={playerSubtitleMode}
                hasTranslation={content.enhancedStatus === "ready"}
                onSubtitleModeChange={setPlayerSubtitleMode}
                summaryThresholdSeconds={summaryThresholdSeconds}
                selectedVoiceoverId={selectedVoiceoverId}
                quickToggleOriginalVoiceoverId={quickToggleOriginalVoiceoverId}
                quickToggleTranslatedVoiceoverId={quickToggleTranslatedVoiceoverId}
                onVoiceoverChange={setSelectedVoiceoverId}
                skipRamblingEnabled={skipRamblingEnabled}
                timelineEntries={timelineEntries}
                onAddToAsk={handlers.handleAddToAsk}
                onAddToNotes={handlers.handleAddToNotes}
            />

            {headerActions}

            {live2dEnabled && (
                <ErrorBoundary
                    component="Live2DCanvas"
                    fallback={
                        <div className="fixed bottom-4 right-4 p-4 bg-muted rounded-lg shadow-lg">
                            <p className="text-sm text-destructive">Live2D failed to load</p>
                            <button
                                onClick={toggleLive2d}
                                className="mt-2 text-xs text-muted-foreground hover:text-foreground"
                            >
                                Close
                            </button>
                        </div>
                    }
                >
                    <Live2DCanvas
                        ref={live2dRef}
                        modelPath={live2dModelPath}
                        initialPosition={live2dModelPosition}
                        initialScale={live2dModelScale}
                        onPositionChange={setLive2dModelPosition}
                        onScaleChange={setLive2dModelScale}
                        onClose={toggleLive2d}
                        onLoad={onLive2DLoad}
                    />
                </ErrorBoundary>
            )}

            {/* DragOverlay for smooth dragging visuals */}
            <DragOverlay>
                {activeId ? (
                    <div className="px-3 py-2 text-sm font-medium rounded-md border border-primary/20 bg-popover shadow-xl ring-2 ring-primary/20 backdrop-blur-sm scale-105 rotate-2 opacity-90 flex items-center gap-1.5">
                        {TAB_CONFIG[activeId]?.icon}
                        <span>{TAB_CONFIG[activeId]?.label}</span>
                    </div>
                ) : null}
            </DragOverlay>
        </div>
        </DndContext>
        </VideoConfigProvider>
    );
}
