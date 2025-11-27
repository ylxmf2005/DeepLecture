"use client";

import { useEffect, useRef, useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { VideoPlayerRef } from "@/components/VideoPlayer";
import { SettingsDialog } from "@/components/SettingsDialog";
import { ActionsDialog } from "@/components/ActionsDialog";
import { getVideoNote, generateVideoNote, getJobStatus } from "@/lib/api";
import { useVideoSettings } from "@/hooks/useVideoSettings";
import { useVideoPageState } from "@/hooks/useVideoPageState";
import { useSmartSkip } from "@/hooks/useSmartSkip";
import { useSubtitleRepeat } from "@/hooks/useSubtitleRepeat";
import { useVideoPageHandlers } from "@/hooks/useVideoPageHandlers";
import { useSubtitleManagement, type SubtitleMode } from "@/hooks/useSubtitleManagement";
import { useVideoProgress, RESUME_TOLERANCE_SECONDS, RESUME_MAX_ATTEMPTS } from "@/hooks/useVideoProgress";
import { useThrottledTimeUpdate } from "@/hooks/useThrottledTimeUpdate";
import { Settings, Wand2, Loader2 } from "lucide-react";
import dynamic from "next/dynamic";
import type { Live2DCanvasHandle } from "@/components/Live2DCanvas";

const Live2DCanvas = dynamic(() => import("@/components/Live2DCanvas"), { ssr: false });
import { useLearnerProfile } from "@/components/LearnerProfileProvider";
import { VideoPlayerSection, NotesPanel, SidebarTabs } from "@/components/video";
import { HeaderActionPortal } from "@/components/HeaderActionPortal";
import { FocusModeHandler } from "@/components/FocusModeHandler";
import { useSidebarSubtitleMode as useSidebarSubtitleModeStore, useVideoDeck, useSmartSkipEnabled, useVideoStateStore } from "@/stores";
import type { CrepeEditor } from "@/components/MarkdownNoteEditor";

export { type ProcessingAction } from "@/hooks/useVideoPageState";

const SIDEBAR_SUBTITLE_MODE_KEY_PREFIX = "courseSubtitle:subtitle-mode:sidebar";
const buildSidebarSubtitleModeKey = (videoId: string) => `${SIDEBAR_SUBTITLE_MODE_KEY_PREFIX}:${videoId}`;

export default function VideoPage() {
    const params = useParams();
    const videoId = params.id as string;

    // Learner profile
    const { profile: learnerProfile, setProfile: setLearnerProfile } = useLearnerProfile();
    const [draftLearnerProfile, setDraftLearnerProfile] = useState<string>(learnerProfile);

    // Video settings
    const {
        autoPauseOnLeave,
        autoResumeOnReturn,
        summaryThresholdSeconds,
        subtitleContextWindowSeconds,
        subtitleRepeatCount,
        subtitleFontSize,
        subtitleBottomOffset,
        originalLanguage,
        aiLanguage,
        translatedLanguage,
        toggleAutoPause,
        toggleAutoResume,
        setSummaryThresholdSeconds,
        setSubtitleContextWindowSeconds,
        setSubtitleRepeatCount,
        setSubtitleFontSize,
        setSubtitleBottomOffset,
        setOriginalLanguage,
        setAiLanguage,
        setTranslatedLanguage,
        hideSidebars,
        toggleHideSidebars,
        live2dEnabled,
        live2dModelPath,
        live2dModelPosition,
        live2dModelScale,
        live2dSyncWithVideoAudio,
        toggleLive2d,
        setLive2dModelPath,
        setLive2dModelPosition,
        setLive2dModelScale,
        toggleLive2dSyncWithVideo,
    } = useVideoSettings();

    // Core page state
    const pageState = useVideoPageState({ videoId, aiLanguage, learnerProfile });
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
        timelineEntries,
        setTimelineEntries,
        timelineLoading,
        setTimelineLoading,
        activeTab,
        setActiveTab,
        currentTime,
        setCurrentTime,
        refreshExplanations,
        setRefreshExplanations,
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
    const toggleSmartSkipStore = useVideoStateStore((store) => store.toggleSmartSkip);

    // Subtitle management
    const {
        subtitlesEn,
        subtitlesZh,
        subtitlesEnZh,
        subtitlesZhEn,
        subtitlesLoading,
        playerTracks,
        subtitleMode: playerSubtitleMode,
        setSubtitleMode: setPlayerSubtitleMode,
        currentSubtitles: playerSubtitles,
    } = useSubtitleManagement({ videoId, content });

    const sidebarSubtitleMode = useSidebarSubtitleModeStore(videoId);

    // Compute sidebar subtitles
    const sidebarSubtitles = useMemo(() => {
        if (sidebarSubtitleMode === "en_zh" && subtitlesEnZh.length > 0) return subtitlesEnZh;
        if (sidebarSubtitleMode === "zh_en" && subtitlesZhEn.length > 0) return subtitlesZhEn;
        if (sidebarSubtitleMode === "zh" && subtitlesZh.length > 0) return subtitlesZh;
        return subtitlesEn;
    }, [sidebarSubtitleMode, subtitlesEn, subtitlesZh, subtitlesEnZh, subtitlesZhEn]);

    // Refs
    const noteEditorRef = useRef<CrepeEditor | null>(null);
    const live2dRef = useRef<Live2DCanvasHandle | null>(null);
    const playerRef = useRef<VideoPlayerRef>(null);

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
        translatedLanguage,
        aiLanguage,
        learnerProfile,
        subtitleContextWindowSeconds,
        subtitlesEn,
        playerSubtitles,
        voiceoverName,
        noteEditorRef,
        setProcessing,
        setProcessingAction,
        setActiveTab,
        setRefreshExplanations,
        setVoiceoverProcessing,
        setVoiceovers,
        setTimelineLoading,
        setTimelineEntries,
        setAskContext,
        setDeckStore,
        hasSubtitles: content?.subtitleStatus === "ready",
        hasEnhancedSubtitles: content?.enhancedStatus === "ready",
    });

    // Migrate localStorage to store
    useEffect(() => {
        if (typeof window === "undefined" || !videoId) return;

        const sidebarKey = buildSidebarSubtitleModeKey(videoId);
        const storedSidebar = window.localStorage.getItem(sidebarKey);
        if (storedSidebar === "en" || storedSidebar === "zh" || storedSidebar === "en_zh" || storedSidebar === "zh_en") {
            setSubtitleModeSidebarStore(videoId, storedSidebar as SubtitleMode);
            window.localStorage.removeItem(sidebarKey);
        }

        const deckKey = `courseSubtitle:video-deck:${videoId}`;
        const rawDeck = window.localStorage.getItem(deckKey);
        if (rawDeck) {
            const parsed = JSON.parse(rawDeck) as { id: string; name: string };
            if (parsed?.id && parsed?.name) {
                setDeckStore(videoId, parsed);
            }
            window.localStorage.removeItem(deckKey);
        }
    }, [videoId, setSubtitleModeSidebarStore, setDeckStore]);

    // Reset repeat state when video/subtitles change
    useEffect(() => {
        resetRepeatState();
    }, [videoId, selectedVoiceoverId, playerSubtitles, resetRepeatState]);

    // Keep draft profile in sync
    useEffect(() => {
        setDraftLearnerProfile(learnerProfile);
    }, [learnerProfile]);

    // Reset Smart Skip when learner profile changes
    useEffect(() => {
        if (!videoId) return;
        setSmartSkipEnabledStore(videoId, false);
    }, [learnerProfile, videoId, setSmartSkipEnabledStore]);

    // Reconnect Live2D audio on model change
    useEffect(() => {
        if (!live2dEnabled || !live2dSyncWithVideoAudio || !live2dRef.current || !playerRef.current) return;

        const videoElement = playerRef.current.getVideoElement?.();
        if (!videoElement) return;

        try {
            live2dRef.current.connectAudioForLipSync(videoElement);
        } catch (error) {
            console.error("Failed to reconnect video audio to Live2D after model change:", error);
        }
    }, [live2dModelPath, live2dEnabled, live2dSyncWithVideoAudio]);

    // Note editor ready callback
    const handleNoteEditorReady = useCallback((editor: CrepeEditor) => {
        noteEditorRef.current = editor;
    }, []);

    // Generate note handler
    const handleGenerateNote = useCallback(async () => {
        if (!videoId || generatingNote) return;

        const editor = noteEditorRef.current;
        if (!editor) {
            alert("Notes editor is not ready yet.");
            return;
        }

        try {
            setGeneratingNote(true);
            const start = await generateVideoNote({ videoId, contextMode: "auto", learnerProfile });
            const jobId = start.job_id;

            if (start.status === "ready" || !jobId) {
                const note = await getVideoNote(videoId);
                editor.setMarkdown(note.content || "");
                setGeneratingNote(false);
                return;
            }

            const maxAttempts = 120;
            const delayMs = 5000;

            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                const job = await getJobStatus(jobId);

                if (job.status === "ready") {
                    const note = await getVideoNote(videoId);
                    editor.setMarkdown(note.content || "");
                    setGeneratingNote(false);
                    return;
                }

                if (job.status === "error") {
                    console.error("Note generation job failed:", job);
                    alert(job.error || "Note generation failed.");
                    setGeneratingNote(false);
                    return;
                }

                await new Promise((resolve) => window.setTimeout(resolve, delayMs));
            }

            setGeneratingNote(false);
            alert("Note generation is taking longer than expected. Please try again later.");
        } catch (error) {
            console.error("Failed to generate note:", error);
            alert("Failed to generate note. Please check the console for details.");
            setGeneratingNote(false);
        }
    }, [videoId, learnerProfile, generatingNote, setGeneratingNote]);

    // Toggle Smart Skip handler
    const handleToggleSkipRambling = useCallback(() => {
        if (content?.subtitleStatus !== "ready" || !videoId) return;
        toggleSmartSkipStore(videoId);
    }, [content?.subtitleStatus, videoId, toggleSmartSkipStore]);

    // Player ready handler
    const handlePlayerReady = useCallback(
        (videoElement: HTMLVideoElement) => {
            if (live2dEnabled && live2dSyncWithVideoAudio && live2dRef.current) {
                try {
                    live2dRef.current.connectAudioForLipSync(videoElement);
                } catch (error) {
                    console.error("Failed to connect video audio to Live2D:", error);
                }
            }

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
                    console.warn("Failed to apply saved progress:", error);
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
        [clearProgress, lastPersistedProgressRef, resumeAttemptsRef, resumeTargetRef, setCurrentTime, live2dEnabled, live2dSyncWithVideoAudio]
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
        <div className={`grid gap-6 h-[130vh] ${hideSidebars ? "grid-cols-1" : "grid-cols-1 md:grid-cols-3"}`}>
            {/* Left Column: Video Player & Notes */}
            <div className={`flex flex-col gap-4 h-full min-h-0 ${hideSidebars ? "col-span-1" : "md:col-span-2"}`}>
                <VideoPlayerSection
                    ref={playerRef}
                    content={content}
                    videoId={videoId}
                    selectedVoiceoverId={selectedVoiceoverId}
                    playerTracks={playerTracks}
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
                />
                {!hideSidebars && (
                    <NotesPanel videoId={videoId} onEditorReady={handleNoteEditorReady} />
                )}
            </div>

            {/* Right Column: Tabs */}
            {!hideSidebars && (
                <SidebarTabs
                    content={content}
                    videoId={videoId}
                    currentTime={currentTime}
                    activeTab={activeTab}
                    setActiveTab={setActiveTab}
                    sidebarSubtitleMode={sidebarSubtitleMode}
                    setSidebarSubtitleMode={(mode) => setSubtitleModeSidebarStore(videoId, mode)}
                    sidebarSubtitles={sidebarSubtitles}
                    subtitlesZh={subtitlesZh}
                    subtitlesEnZh={subtitlesEnZh}
                    subtitlesZhEn={subtitlesZhEn}
                    subtitlesLoading={subtitlesLoading}
                    processing={processing}
                    processingAction={processingAction}
                    timelineEntries={timelineEntries}
                    timelineLoading={timelineLoading}
                    refreshExplanations={refreshExplanations}
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

            <SettingsDialog
                isOpen={isSettingsOpen}
                onClose={() => setIsSettingsOpen(false)}
                video={content}
                learnerProfile={learnerProfile}
                setLearnerProfile={setLearnerProfile}
                draftLearnerProfile={draftLearnerProfile}
                setDraftLearnerProfile={setDraftLearnerProfile}
                originalLanguage={originalLanguage}
                setOriginalLanguage={setOriginalLanguage}
                aiLanguage={aiLanguage}
                setAiLanguage={setAiLanguage}
                translatedLanguage={translatedLanguage}
                setTranslatedLanguage={setTranslatedLanguage}
                subtitleContextWindowSeconds={subtitleContextWindowSeconds}
                setSubtitleContextWindowSeconds={setSubtitleContextWindowSeconds}
                subtitleRepeatCount={subtitleRepeatCount}
                setSubtitleRepeatCount={setSubtitleRepeatCount}
                subtitleFontSize={subtitleFontSize}
                setSubtitleFontSize={setSubtitleFontSize}
                subtitleBottomOffset={subtitleBottomOffset}
                setSubtitleBottomOffset={setSubtitleBottomOffset}
                autoPauseOnLeave={autoPauseOnLeave}
                handleToggleAutoPause={toggleAutoPause}
                autoResumeOnReturn={autoResumeOnReturn}
                handleToggleAutoResume={toggleAutoResume}
                summaryThresholdSeconds={summaryThresholdSeconds}
                setSummaryThresholdSeconds={setSummaryThresholdSeconds}
                hideSidebars={hideSidebars}
                handleToggleHideSidebars={toggleHideSidebars}
                skipRamblingEnabled={skipRamblingEnabled}
                handleToggleSkipRambling={handleToggleSkipRambling}
                live2dEnabled={live2dEnabled}
                handleToggleLive2d={toggleLive2d}
                live2dModelPath={live2dModelPath}
                setLive2dModelPath={setLive2dModelPath}
                live2dSyncWithVideoAudio={live2dSyncWithVideoAudio}
                handleToggleLive2dSyncWithVideo={toggleLive2dSyncWithVideo}
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
                <Live2DCanvas
                    ref={live2dRef}
                    modelPath={live2dModelPath}
                    initialPosition={live2dModelPosition}
                    initialScale={live2dModelScale}
                    onPositionChange={setLive2dModelPosition}
                    onScaleChange={setLive2dModelScale}
                    onClose={toggleLive2d}
                />
            )}
        </div>
    );
}
