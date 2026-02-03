"use client";

import { useEffect, useRef, useCallback, useMemo, useId } from "react";
import dynamic from "next/dynamic";
import { VideoPlayerRef } from "@/components/video/VideoPlayer";
import type { ContentItem, VoiceoverEntry } from "@/lib/api";
import { useVideoPageState } from "@/hooks/useVideoPageState";
import { useSmartSkip } from "@/hooks/useSmartSkip";
import { useSubtitleRepeat } from "@/hooks/useSubtitleRepeat";
import { useVideoPageHandlers } from "@/hooks/useVideoPageHandlers";
import { useSubtitleManagement } from "@/hooks/useSubtitleManagement";
import { SubtitleDisplayMode } from "@/stores/types";
import { useVideoProgress, RESUME_TOLERANCE_SECONDS, RESUME_MAX_ATTEMPTS } from "@/hooks/useVideoProgress";
import { useThrottledTimeUpdate } from "@/hooks/useThrottledTimeUpdate";
import { useNoteGeneration } from "@/hooks/useNoteGeneration";
import { useDndTabLayout } from "@/hooks/useDndTabLayout";
import { useLive2DAudioSync } from "@/hooks/useLive2DAudioSync";
import { Settings, Wand2, Loader2 } from "lucide-react";
import { DndContext, DragOverlay } from "@dnd-kit/core";

// Lazy load dialogs - only loaded when opened
const SettingsDialog = dynamic(
    () => import("@/components/dialogs/SettingsDialog").then((mod) => mod.SettingsDialog),
    { ssr: false }
);
const ActionsDialog = dynamic(
    () => import("@/components/dialogs/ActionsDialog").then((mod) => mod.ActionsDialog),
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
} from "@/stores";
import { useVideoPageSettings } from "@/hooks/useVideoPageSettings";
import { TAB_CONFIG } from "@/components/dnd/DraggableTabBar";

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
        subtitleRefreshVersion,
        askContext,
        setAskContext,
        isSettingsOpen,
        setIsSettingsOpen,
        isActionsOpen,
        setIsActionsOpen,
        generatingNote,
        setGeneratingNote,
        tasks,
    } = pageState;

    // Store hooks
    const skipRamblingEnabled = useSmartSkipEnabled(videoId);
    const deck = useVideoDeck(videoId);
    const setSubtitleModeSidebarStore = useVideoStateStore((store) => store.setSubtitleModeSidebar);
    const setDeckStore = useVideoStateStore((store) => store.setDeck);
    const setSmartSkipEnabledStore = useVideoStateStore((store) => store.setSmartSkipEnabled);

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

    // Refs
    const playerRef = useRef<VideoPlayerRef>(null);

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
        tasks,
        confirm,
    });

    // Video progress persistence
    const {
        resumeTargetRef,
        resumeAttemptsRef,
        lastPersistedProgressRef,
        maybePersistProgress,
        clearProgress,
    } = useVideoProgress({ videoId, playerRef });

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

    // Player ready handler
    const handlePlayerReady = useCallback(
        (videoElement: HTMLVideoElement) => {
            // Connect Live2D audio sync (handled by extracted hook)
            connectLive2DAudio(videoElement);

            if (resumeTargetRef.current === null || resumeTargetRef.current <= 0) return;

            resumeAttemptsRef.current = 0;

            const clampTarget = (target: number) => {
                const duration = videoElement.duration;
                if (!Number.isFinite(duration) || duration <= 0) return Math.max(0, target);
                const maxPlayable = Math.max(duration - RESUME_TOLERANCE_SECONDS, 0);
                return Math.min(Math.max(target, 0), maxPlayable);
            };

            const trySeek = () => {
                const target = resumeTargetRef.current;
                if (target === null) return;
                const safeTarget = clampTarget(target);

                try {
                    videoElement.currentTime = safeTarget;
                } catch (error) {
                    log.warn("Failed to apply saved progress", { error: error instanceof Error ? error.message : String(error) });
                }

                window.setTimeout(() => {
                    const delta = Math.abs(videoElement.currentTime - safeTarget);
                    if (delta <= RESUME_TOLERANCE_SECONDS) {
                        resumeTargetRef.current = null;
                        resumeAttemptsRef.current = 0;
                        lastPersistedProgressRef.current = videoElement.currentTime;
                        setCurrentTime(videoElement.currentTime);
                    } else if (resumeAttemptsRef.current < RESUME_MAX_ATTEMPTS) {
                        resumeAttemptsRef.current += 1;
                        trySeek();
                    } else {
                        resumeTargetRef.current = null;
                        resumeAttemptsRef.current = 0;
                        clearProgress();
                        lastPersistedProgressRef.current = 0;
                        videoElement.currentTime = 0;
                        setCurrentTime(0);
                    }
                }, 250);
            };

            trySeek();
        },
        [clearProgress, lastPersistedProgressRef, resumeAttemptsRef, resumeTargetRef, setCurrentTime, connectLive2DAudio]
    );

    // Loading state
    if (loading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            </div>
        );
    }

    // Not found state
    if (!content) {
        return (
            <div className="text-center py-12">
                <h2 className="text-xl font-semibold">Content not found</h2>
            </div>
        );
    }

    return (
        <DndContext
            id={dndContextId}
            sensors={sensors}
            collisionDetection={collisionDetection}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
            onDragCancel={handleDragCancel}
        >
            <div className={`grid gap-6 h-[130vh] ${
                hideSidebars
                    ? "grid-cols-1"
                    : viewMode === "widescreen"
                        ? "grid-cols-1"
                        : "grid-cols-1 md:grid-cols-3"
            }`}>
                {/* Video Player Column - full width in widescreen mode */}
                <div className={`flex flex-col gap-4 ${
                    viewMode === "widescreen"
                        ? "col-span-1"
                        : hideSidebars
                            ? "col-span-1"
                            : "md:col-span-2"
                } ${viewMode === "widescreen" ? "" : "h-full min-h-0"}`}>
                    {/* Video Title and Metadata */}
                    <div className="flex items-baseline justify-between gap-4">
                        <h1 className="text-xl font-semibold truncate">{content.filename}</h1>
                        <span className="text-sm text-muted-foreground whitespace-nowrap">
                            {new Date(content.createdAt).toLocaleDateString(undefined, {
                                year: "numeric",
                                month: "short",
                                day: "numeric"
                            })}
                        </span>
                    </div>
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
                        />
                    </ErrorBoundary>

                    {/* NotesPanel in normal mode (not widescreen) */}
                    {!hideSidebars && viewMode !== "widescreen" && (
                        <NotesPanel
                            videoId={videoId}
                            onEditorReady={handleNoteEditorReady}
                            content={content}
                            currentTime={currentTime}
                            sidebarSubtitleMode={sidebarSubtitleMode}
                            setSidebarSubtitleMode={(mode) => setSubtitleModeSidebarStore(videoId, mode)}
                            sidebarSubtitles={sidebarSubtitles}
                            subtitlesTarget={subtitlesTarget}
                            subtitlesDual={subtitlesDual}
                            subtitlesDualReversed={subtitlesDualReversed}
                            subtitlesLoading={subtitlesLoading}
                            processing={processing}
                            processingAction={processingAction}
                            timelineEntries={timelineEntries}
                            timelineLoading={timelineLoading}
                            refreshExplanations={refreshExplanations}
                            refreshVerification={refreshVerification}
                            refreshCheatsheet={refreshCheatsheet}
                            askContext={askContext}
                            learnerProfile={learnerProfile}
                            subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                            onSeek={handleSeek}
                            onAddToAsk={handlers.handleAddToAsk}
                            onAddToNotes={handlers.handleAddToNotes}
                            onRemoveFromAsk={handlers.handleRemoveFromAsk}
                            onGenerateSubtitles={handlers.handleGenerateSubtitles}
                            onGenerateTimeline={handlers.handleGenerateTimeline}
                        />
                    )}
                </div>

                {/* Sidebar in normal mode (not widescreen) */}
                {!hideSidebars && viewMode !== "widescreen" && (
                    <SidebarTabs
                        content={content}
                        videoId={videoId}
                        currentTime={currentTime}
                        sidebarSubtitleMode={sidebarSubtitleMode}
                        setSidebarSubtitleMode={(mode) => setSubtitleModeSidebarStore(videoId, mode)}
                        sidebarSubtitles={sidebarSubtitles}
                        subtitlesTarget={subtitlesTarget}
                        subtitlesDual={subtitlesDual}
                        subtitlesDualReversed={subtitlesDualReversed}
                        subtitlesLoading={subtitlesLoading}
                        processing={processing}
                        processingAction={processingAction}
                        timelineEntries={timelineEntries}
                        timelineLoading={timelineLoading}
                        refreshExplanations={refreshExplanations}
                        refreshVerification={refreshVerification}
                        refreshCheatsheet={refreshCheatsheet}
                        askContext={askContext}
                        learnerProfile={learnerProfile}
                        subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                        onSeek={handleSeek}
                        onAddToAsk={handlers.handleAddToAsk}
                        onAddToNotes={handlers.handleAddToNotes}
                        onRemoveFromAsk={handlers.handleRemoveFromAsk}
                        onGenerateSubtitles={handlers.handleGenerateSubtitles}
                        onGenerateTimeline={handlers.handleGenerateTimeline}
                    />
                )}

                {/* Widescreen mode: NotesPanel and Sidebar side by side below video */}
                {!hideSidebars && viewMode === "widescreen" && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-[80vh]">
                        <NotesPanel
                            videoId={videoId}
                            onEditorReady={handleNoteEditorReady}
                            content={content}
                            currentTime={currentTime}
                            sidebarSubtitleMode={sidebarSubtitleMode}
                            setSidebarSubtitleMode={(mode) => setSubtitleModeSidebarStore(videoId, mode)}
                            sidebarSubtitles={sidebarSubtitles}
                            subtitlesTarget={subtitlesTarget}
                            subtitlesDual={subtitlesDual}
                            subtitlesDualReversed={subtitlesDualReversed}
                            subtitlesLoading={subtitlesLoading}
                            processing={processing}
                            processingAction={processingAction}
                            timelineEntries={timelineEntries}
                            timelineLoading={timelineLoading}
                            refreshExplanations={refreshExplanations}
                            refreshVerification={refreshVerification}
                            refreshCheatsheet={refreshCheatsheet}
                            askContext={askContext}
                            learnerProfile={learnerProfile}
                            subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                            onSeek={handleSeek}
                            onAddToAsk={handlers.handleAddToAsk}
                            onAddToNotes={handlers.handleAddToNotes}
                            onRemoveFromAsk={handlers.handleRemoveFromAsk}
                            onGenerateSubtitles={handlers.handleGenerateSubtitles}
                            onGenerateTimeline={handlers.handleGenerateTimeline}
                        />
                        <SidebarTabs
                            content={content}
                            videoId={videoId}
                            currentTime={currentTime}
                            sidebarSubtitleMode={sidebarSubtitleMode}
                            setSidebarSubtitleMode={(mode) => setSubtitleModeSidebarStore(videoId, mode)}
                            sidebarSubtitles={sidebarSubtitles}
                            subtitlesTarget={subtitlesTarget}
                            subtitlesDual={subtitlesDual}
                            subtitlesDualReversed={subtitlesDualReversed}
                            subtitlesLoading={subtitlesLoading}
                            processing={processing}
                            processingAction={processingAction}
                            timelineEntries={timelineEntries}
                            timelineLoading={timelineLoading}
                            refreshExplanations={refreshExplanations}
                            refreshVerification={refreshVerification}
                            refreshCheatsheet={refreshCheatsheet}
                            askContext={askContext}
                            learnerProfile={learnerProfile}
                            subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                            onSeek={handleSeek}
                            onAddToAsk={handlers.handleAddToAsk}
                            onAddToNotes={handlers.handleAddToNotes}
                            onRemoveFromAsk={handlers.handleRemoveFromAsk}
                            onGenerateSubtitles={handlers.handleGenerateSubtitles}
                            onGenerateTimeline={handlers.handleGenerateTimeline}
                        />
                    </div>
                )}

            <SettingsDialog
                isOpen={isSettingsOpen}
                onClose={() => setIsSettingsOpen(false)}
                video={content}
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
                currentTime={currentTime}
                learnerProfile={learnerProfile}
                autoPauseOnLeave={autoPauseOnLeave}
                autoResumeOnReturn={autoResumeOnReturn}
                summaryThresholdSeconds={summaryThresholdSeconds}
                skipRamblingEnabled={skipRamblingEnabled}
                timelineEntries={timelineEntries}
                onAddToAsk={handlers.handleAddToAsk}
                onAddToNotes={handlers.handleAddToNotes}
            />

            <HeaderActionPortal>
                <button
                    onClick={() => setIsActionsOpen(true)}
                    className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                    title="Actions"
                >
                    <Wand2 className="w-5 h-5" />
                </button>
                <button
                    onClick={() => setIsSettingsOpen(true)}
                    className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                    title="Settings"
                >
                    <Settings className="w-5 h-5" />
                </button>
            </HeaderActionPortal>

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
    );
}
