import { X, Globe, Sparkles, BrainCircuit, MessageSquare, User, Loader2, Cpu, Settings, PlayCircle, Subtitles, Zap, ListVideo, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { CustomSelect } from "@/components/ui/CustomSelect";
import {
    ContentItem,
    getLive2DModels,
    Live2DModel,
    getLLMModels,
    LLMModelInfo,
    getTTSModels,
    TTSModelInfo,
} from "@/lib/api";

export interface SettingsDialogProps {
    isOpen: boolean;
    onClose: () => void;
    video: ContentItem;
    // Learning Preferences
    learnerProfile: string;
    setLearnerProfile: (profile: string) => void;
    draftLearnerProfile: string;
    setDraftLearnerProfile: (profile: string) => void;
    // Language Settings
    originalLanguage: string;
    setOriginalLanguage: (value: string) => void;
    aiLanguage: string;
    setAiLanguage: (value: string) => void;
    translatedLanguage: string;
    setTranslatedLanguage: (value: string) => void;
    // AI Context
    subtitleContextWindowSeconds: number;
    setSubtitleContextWindowSeconds: (seconds: number) => void;
    subtitleRepeatCount: number;
    setSubtitleRepeatCount: (value: number) => void;
    // Focus Mode
    autoPauseOnLeave: boolean;
    handleToggleAutoPause: () => void;
    autoResumeOnReturn: boolean;
    handleToggleAutoResume: () => void;
    summaryThresholdSeconds: number;
    setSummaryThresholdSeconds: (seconds: number) => void;
    hideSidebars: boolean;
    handleToggleHideSidebars: () => void;
    // Subtitle display
    subtitleFontSize: number;
    setSubtitleFontSize: (size: number) => void;
    subtitleBottomOffset: number;
    setSubtitleBottomOffset: (offset: number) => void;
    // Smart Skip (moved from Timeline & Playback)
    skipRamblingEnabled: boolean;
    handleToggleSkipRambling: () => void;
    // Live2D settings
    live2dEnabled: boolean;
    handleToggleLive2d: () => void;
    live2dModelPath: string;
    setLive2dModelPath: (path: string) => void;
    live2dSyncWithVideoAudio: boolean;
    handleToggleLive2dSyncWithVideo: () => void;
}

type TabId = "general" | "player" | "functions" | "model" | "live2d";

export function SettingsDialog({
    isOpen,
    onClose,
    video,
    learnerProfile,
    setLearnerProfile,
    draftLearnerProfile,
    setDraftLearnerProfile,
    originalLanguage,
    setOriginalLanguage,
    aiLanguage,
    setAiLanguage,
    translatedLanguage,
    setTranslatedLanguage,
    subtitleContextWindowSeconds,
    setSubtitleContextWindowSeconds,
    subtitleRepeatCount,
    setSubtitleRepeatCount,
    autoPauseOnLeave,
    handleToggleAutoPause,
    autoResumeOnReturn,
    handleToggleAutoResume,
    summaryThresholdSeconds,
    setSummaryThresholdSeconds,
    hideSidebars,
    handleToggleHideSidebars,
    subtitleFontSize,
    setSubtitleFontSize,
    subtitleBottomOffset,
    setSubtitleBottomOffset,
    skipRamblingEnabled,
    handleToggleSkipRambling,
    live2dEnabled,
    handleToggleLive2d,
    live2dModelPath,
    setLive2dModelPath,
    live2dSyncWithVideoAudio,
    handleToggleLive2dSyncWithVideo,
}: SettingsDialogProps) {
    const [activeTab, setActiveTab] = useState<TabId>("general");
    const [live2dModels, setLive2dModels] = useState<Live2DModel[]>([]);
    const [modelsLoading, setModelsLoading] = useState(false);

    // LLM Model Settings state (read-only)
    const [llmModels, setLlmModels] = useState<LLMModelInfo[]>([]);
    const [taskModels, setTaskModels] = useState<Record<string, string>>({});
    const [defaultModel, setDefaultModel] = useState<string>("");
    const [llmModelsLoading, setLlmModelsLoading] = useState(false);
    // TTS Model Settings state (read-only)
    const [ttsModels, setTtsModels] = useState<TTSModelInfo[]>([]);
    const [ttsTaskModels, setTtsTaskModels] = useState<Record<string, string>>({});
    const [defaultTtsModel, setDefaultTtsModel] = useState<string>("");
    const [ttsLoading, setTtsLoading] = useState(false);

    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        if (isOpen) {
            window.addEventListener("keydown", handleEsc);
            document.body.style.overflow = "hidden";
        }
        return () => {
            window.removeEventListener("keydown", handleEsc);
            document.body.style.overflow = "unset";
        };
    }, [isOpen, onClose]);

    useEffect(() => {
        if (!isOpen || !live2dEnabled) return;
        const fetchModels = async () => {
            setModelsLoading(true);
            try {
                const models = await getLive2DModels();
                setLive2dModels(models);
            } catch (error) {
                console.error("Failed to fetch Live2D models:", error);
            } finally {
                setModelsLoading(false);
            }
        };
        fetchModels();
    }, [isOpen, live2dEnabled]);

    useEffect(() => {
        if (!isOpen) return;
        const fetchLLMModels = async () => {
            setLlmModelsLoading(true);
            try {
                const data = await getLLMModels();
                setLlmModels(data.models);
                setTaskModels(data.task_models);
                setDefaultModel(data.default);
            } catch (error) {
                console.error("Failed to fetch LLM models:", error);
            } finally {
                setLlmModelsLoading(false);
            }
        };
        fetchLLMModels();
    }, [isOpen]);

    useEffect(() => {
        if (!isOpen) return;
        const fetchTTSModels = async () => {
            setTtsLoading(true);
            try {
                const data = await getTTSModels();
                // Defensive parsing: API should return models/task_models/default, but guard against null/shape drift
                const models = Array.isArray(data?.models) ? data.models : [];
                const taskModels =
                    data && typeof data === "object" && "task_models" in data && typeof data.task_models === "object"
                        ? data.task_models
                        : {};

                setTtsModels(models);
                setTtsTaskModels(taskModels);
                setDefaultTtsModel(typeof data?.default === "string" ? data.default : "");
            } catch (error) {
                console.error("Failed to fetch TTS models:", error);
                setTtsModels([]);
                setTtsTaskModels({});
                setDefaultTtsModel("");
            } finally {
                setTtsLoading(false);
            }
        };
        fetchTTSModels();
    }, [isOpen]);

    if (!isOpen) return null;

    const tabs = [
        { id: "general" as const, label: "General", icon: Settings },
        { id: "player" as const, label: "Player", icon: PlayCircle },
        { id: "functions" as const, label: "Functions", icon: Zap },
        { id: "model" as const, label: "Model", icon: Cpu },
        { id: "live2d" as const, label: "Live2D", icon: User },
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div
                className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Settings</h2>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Main content area with tabs */}
                <div className="flex flex-1 overflow-hidden">
                    {/* Sidebar navigation */}
                    <div className="w-48 bg-gray-50 dark:bg-gray-900/50 border-r border-gray-200 dark:border-gray-800">
                        <nav className="p-2 space-y-1">
                            {tabs.map((tab) => {
                                const Icon = tab.icon;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={cn(
                                            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                                            activeTab === tab.id
                                                ? "bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm"
                                                : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800/50"
                                        )}
                                    >
                                        <Icon className={cn(
                                            "w-4 h-4",
                                            activeTab === tab.id ? "text-blue-600 dark:text-blue-400" : "text-gray-400"
                                        )} />
                                        {tab.label}
                                    </button>
                                );
                            })}
                        </nav>
                    </div>

                    {/* Content area */}
                    <div className="flex-1 overflow-y-auto p-6 bg-gray-50/50 dark:bg-gray-900/50">
                        <div className="max-w-3xl space-y-8">
                            {/* General Tab */}
                            {activeTab === "general" && (
                                <>
                                    {/* Learning Preferences Section */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                                            <BrainCircuit className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Learning Preferences</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-100 dark:border-gray-700 space-y-3">
                                            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                                Customize your AI learning experience. Tell us about your background and goals to get tailored explanations and notes.
                                            </p>
                                            <div className="relative">
                                                <textarea
                                                    value={draftLearnerProfile}
                                                    onChange={(e) => setDraftLearnerProfile(e.target.value)}
                                                    rows={4}
                                                    placeholder="e.g. I know basic Python, I am preparing for the final exam, please skip trivial chit-chat and focus on problem-solving steps."
                                                    className="w-full px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-sm resize-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-gray-400"
                                                />
                                                <div className="absolute bottom-3 right-3">
                                                    {learnerProfile && (
                                                        <span className="text-[10px] text-gray-400 bg-white dark:bg-gray-800 px-2 py-1 rounded-full border border-gray-100 dark:border-gray-700 shadow-sm">
                                                            {learnerProfile.length} chars
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex justify-end">
                                                <button
                                                    type="button"
                                                    onClick={() => setLearnerProfile(draftLearnerProfile.trim())}
                                                    className="inline-flex items-center px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors shadow-sm hover:shadow-md active:scale-95"
                                                >
                                                    <Sparkles className="w-3 h-3 mr-2" />
                                                    Apply Preferences
                                                </button>
                                            </div>
                                        </div>
                                    </section>

                                    {/* Language Settings Section */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                                            <Globe className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Language Settings</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
                                            <div className="space-y-2">
                                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                                    Original Subtitle Language
                                                </label>
                                                <CustomSelect
                                                    value={originalLanguage}
                                                    onChange={setOriginalLanguage}
                                                    options={[
                                                        { value: "en", label: "English" },
                                                        { value: "zh", label: "Chinese" },
                                                    ]}
                                                    accent="emerald"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                    Used when generating subtitles from the video audio. Only English and Chinese are supported.
                                                </p>
                                            </div>

                                            <div className="space-y-2">
                                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                                    AI Explanation Language
                                                </label>
                                                <input
                                                    type="text"
                                                    value={aiLanguage}
                                                    onChange={(e) => setAiLanguage(e.target.value)}
                                                    placeholder="Simplified Chinese or zh"
                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                    Controls the language used for timelines, Ask answers, and slide explanations.
                                                </p>
                                            </div>

                                            <div className="space-y-2">
                                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                                    Translated Subtitle Language
                                                </label>
                                                <input
                                                    type="text"
                                                    value={translatedLanguage}
                                                    onChange={(e) => setTranslatedLanguage(e.target.value)}
                                                    placeholder="zh"
                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                    Used for translated subtitles and as the default voiceover language.
                                                </p>
                                            </div>
                                        </div>
                                    </section>
                                </>
                            )}

                            {/* Player Tab */}
                            {activeTab === "player" && (
                                <>
                                    {/* Subtitle Display Section */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-violet-600 dark:text-violet-400">
                                            <Subtitles className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Subtitle Display</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
                                            <div className="space-y-2">
                                                <div className="flex items-baseline justify-between gap-4">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">
                                                        Subtitle Size
                                                    </span>
                                                    <span className="text-sm font-semibold text-violet-600 dark:text-violet-400 whitespace-nowrap">
                                                        {subtitleFontSize}px
                                                    </span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min={10}
                                                    max={40}
                                                    step={1}
                                                    value={subtitleFontSize}
                                                    onChange={(e) => setSubtitleFontSize(Number(e.target.value))}
                                                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                                    Adjusts the base subtitle font size for the video player. Fullscreen mode may render slightly larger.
                                                </p>
                                            </div>

                                            <div className="space-y-2 pt-3 border-t border-gray-100 dark:border-gray-700">
                                                <div className="flex items-baseline justify-between gap-4">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">
                                                        Vertical Position
                                                    </span>
                                                    <span className="text-sm font-semibold text-violet-600 dark:text-violet-400 whitespace-nowrap">
                                                        {subtitleBottomOffset}px from bottom
                                                    </span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min={0}
                                                    max={160}
                                                    step={4}
                                                    value={subtitleBottomOffset}
                                                    onChange={(e) => setSubtitleBottomOffset(Number(e.target.value))}
                                                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                                    Moves subtitles up or down so they do not overlap with course content or the player controls.
                                                </p>
                                            </div>

                                            <div className="space-y-2 pt-3 border-t border-gray-100 dark:border-gray-700">
                                                <div className="flex items-baseline justify-between gap-4">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">
                                                        Subtitle Repeat Count
                                                    </span>
                                                    <span className="text-sm font-semibold text-violet-600 dark:text-violet-400 whitespace-nowrap">
                                                        ×{subtitleRepeatCount}
                                                    </span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min="1"
                                                    max="5"
                                                    step="1"
                                                    value={subtitleRepeatCount}
                                                    onChange={(e) => setSubtitleRepeatCount(Number(e.target.value))}
                                                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-violet-500"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                                    Controls how many times each subtitle line plays before moving on.
                                                </p>
                                            </div>
                                        </div>
                                    </section>
                                    {/* Focus Mode Section */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
                                            <PlayCircle className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Focus Mode</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
                                            <div className="flex items-center justify-between">
                                                <div className="flex flex-col">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">Auto-pause on Leave</span>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                                        Pause video when you switch tabs
                                                    </span>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={handleToggleAutoPause}
                                                    className={cn(
                                                        "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-rose-500/50",
                                                        autoPauseOnLeave ? "bg-rose-500 border-rose-500" : "bg-gray-200 dark:bg-gray-700 border-gray-300 dark:border-gray-600"
                                                    )}
                                                >
                                                    <span
                                                        className={cn(
                                                            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                                                            autoPauseOnLeave ? "translate-x-5" : "translate-x-1"
                                                        )}
                                                    />
                                                </button>
                                            </div>

                                            <div className="flex items-center justify-between">
                                                <div className="flex flex-col">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">Auto-resume on Return</span>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                                        Resume video when you return
                                                    </span>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={handleToggleAutoResume}
                                                    disabled={!autoPauseOnLeave}
                                                    className={cn(
                                                        "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-rose-500/50",
                                                        autoResumeOnReturn ? "bg-rose-500 border-rose-500" : "bg-gray-200 dark:bg-gray-700 border-gray-300 dark:border-gray-600"
                                                    )}
                                                >
                                                    <span
                                                        className={cn(
                                                            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                                                            autoResumeOnReturn ? "translate-x-5" : "translate-x-1"
                                                        )}
                                                    />
                                                </button>
                                            </div>

                                            <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Summary Threshold</span>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400">{summaryThresholdSeconds} seconds</span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min="10"
                                                    max="300"
                                                    step="10"
                                                    value={summaryThresholdSeconds}
                                                    onChange={(e) => setSummaryThresholdSeconds(Number(e.target.value))}
                                                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-rose-500"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                    Show summary if you missed more than this amount of content.
                                                </p>
                                            </div>

                                            <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-700">
                                                <div className="flex flex-col">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">Immersive Mode</span>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                                        Hide sidebars to focus on the video
                                                    </span>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={handleToggleHideSidebars}
                                                    className={cn(
                                                        "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-rose-500/50",
                                                        hideSidebars ? "bg-rose-500 border-rose-500" : "bg-gray-200 dark:bg-gray-700 border-gray-300 dark:border-gray-600"
                                                    )}
                                                >
                                                    <span
                                                        className={cn(
                                                            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                                                            hideSidebars ? "translate-x-5" : "translate-x-1"
                                                        )}
                                                    />
                                                </button>
                                            </div>
                                        </div>
                                    </section>
                                </>
                            )}


                            {/* Functions Tab */}
                            {activeTab === "functions" && (
                                <>
                                    {/* Timeline Section */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                                            <ListVideo className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Timeline</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700">
                                            <div className="flex items-center justify-between">
                                                <div className="flex flex-col">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">Smart Skip</span>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                                        Automatically skip rambling parts
                                                    </span>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={handleToggleSkipRambling}
                                                    disabled={video?.subtitleStatus !== "ready"}
                                                    className={cn(
                                                        "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-amber-500/50",
                                                        skipRamblingEnabled ? "bg-amber-500 border-amber-500" : "bg-gray-200 dark:bg-gray-700 border-gray-300 dark:border-gray-600"
                                                    )}
                                                >
                                                    <span
                                                        className={cn(
                                                            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                                                            skipRamblingEnabled ? "translate-x-5" : "translate-x-1"
                                                        )}
                                                    />
                                                </button>
                                            </div>
                                        </div>
                                    </section>

                                    {/* Ask AI Section */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-purple-600 dark:text-purple-400">
                                            <MessageSquare className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Ask AI</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
                                            <div className="space-y-3">
                                                <div className="flex items-baseline justify-between gap-4">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">
                                                        Subtitle Context Window
                                                    </span>
                                                    <span className="text-sm font-semibold text-purple-600 dark:text-purple-400 whitespace-nowrap">
                                                        ±{subtitleContextWindowSeconds} seconds
                                                    </span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min="5"
                                                    max="120"
                                                    step="5"
                                                    value={subtitleContextWindowSeconds}
                                                    onChange={(e) => setSubtitleContextWindowSeconds(Number(e.target.value))}
                                                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-purple-500"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                                    Controls how much original-language transcript is included when explaining screenshots or adding video moments to Ask.
                                                </p>
                                            </div>

                                            <div className="space-y-2 pt-3 border-t border-gray-100 dark:border-gray-700">
                                                <div className="flex items-baseline justify-between gap-4">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100">
                                                        Subtitle Repeat Count
                                                    </span>
                                                    <span className="text-sm font-semibold text-purple-600 dark:text-purple-400 whitespace-nowrap">
                                                        ×{subtitleRepeatCount}
                                                    </span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min="1"
                                                    max="5"
                                                    step="1"
                                                    value={subtitleRepeatCount}
                                                    onChange={(e) => setSubtitleRepeatCount(Number(e.target.value))}
                                                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-purple-500"
                                                />
                                                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                                                    Controls how many times each subtitle line plays before moving on.
                                                </p>
                                            </div>
                                        </div>
                                    </section>
                                </>
                            )}


                            {/* Model Tab */}
                            {activeTab === "model" && (
                                <>
                                    {/* AI Model Settings Section (Read-Only) */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
                                            <Cpu className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">AI Model Settings</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-6">
                                            {llmModelsLoading ? (
                                                <div className="flex flex-col items-center justify-center py-8 space-y-3">
                                                    <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
                                                    <span className="text-sm text-gray-500 font-medium">Loading AI models configuration...</span>
                                                </div>
                                            ) : llmModels.length === 0 ? (
                                                <div className="flex flex-col items-center justify-center py-6 text-center">
                                                    <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-full mb-3">
                                                        <Cpu className="w-6 h-6 text-gray-400" />
                                                    </div>
                                                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">No Models Found</p>
                                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-xs">
                                                        Please configure your available models in <code className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 font-mono text-xs">conf.yaml</code>
                                                    </p>
                                                </div>
                                            ) : (
                                                <>
                                                    <div className="space-y-3">
                                                        <div className="flex items-center justify-between">
                                                            <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                                                Available Models
                                                            </label>
                                                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 font-medium">
                                                                {llmModels.length} Active
                                                            </span>
                                                        </div>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            {llmModels.map((m) => (
                                                                <div
                                                                    key={m.name}
                                                                    className="relative flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-xs"
                                                                >
                                                                    {m.name === defaultModel && (
                                                                        <span className="absolute -top-1.5 -right-1.5 px-1.5 py-0.5 rounded-full bg-indigo-600 text-white text-[9px] font-bold uppercase tracking-wider shadow-sm">
                                                                            Default
                                                                        </span>
                                                                    )}
                                                                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                                                                    <span className="font-medium truncate flex-1 text-gray-900 dark:text-gray-100">{m.name}</span>
                                                                    <span className="opacity-60 text-[10px] font-mono shrink-0 text-gray-500 dark:text-gray-400">{m.model}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>

                                                    <div className="space-y-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                                                        <div className="flex items-center gap-2">
                                                            <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                                                Task Assignment
                                                            </label>
                                                            <div className="h-px flex-1 bg-gray-100 dark:bg-gray-700" />
                                                        </div>

                                                        <div className="space-y-2">
                                                            {[
                                                                { key: "slide_lecture", label: "Slide Lecture", desc: "Generates spoken scripts for slides" },
                                                                { key: "note_generation", label: "Note Generation", desc: "Summarizes content into study notes" },
                                                                { key: "subtitle_enhancement", label: "Subtitle Polish", desc: "Cleans up raw speech-to-text" },
                                                                { key: "subtitle_timeline", label: "Timeline Analysis", desc: "Segments video into logical chapters" },
                                                                { key: "ask_video", label: "Ask Video", desc: "Answers questions about video content" },
                                                            ].map(({ key, label, desc }) => (
                                                                <div key={key} className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-4 p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                                                                    <div className="flex flex-col min-w-0">
                                                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</span>
                                                                        <span className="text-[10px] text-gray-400 truncate">{desc}</span>
                                                                    </div>
                                                                    <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400 px-2 py-1 bg-indigo-50 dark:bg-indigo-900/20 rounded">
                                                                        {taskModels[key] || defaultModel}
                                                                    </span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>

                                                    <p className="text-xs text-gray-400 dark:text-gray-500 text-center pt-2">
                                                        Model assignments are configured in <code className="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-700 font-mono text-[10px]">conf.yaml</code>
                                                    </p>
                                                </>
                                            )}
                                        </div>
                                    </section>

                                    {/* TTS Model Settings (Read-Only) */}
                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
                                            <Volume2 className="w-5 h-5" />
                                            <h3 className="font-semibold text-gray-900 dark:text-gray-100">TTS Model Settings</h3>
                                        </div>

                                        <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-6">
                                            {ttsLoading ? (
                                                <div className="flex flex-col items-center justify-center py-6 space-y-3">
                                                    <Loader2 className="w-6 h-6 animate-spin text-rose-500" />
                                                    <span className="text-sm text-gray-500 font-medium">Loading voice models...</span>
                                                </div>
                                            ) : ttsModels.length === 0 ? (
                                                <div className="flex flex-col items-center justify-center py-6 text-center">
                                                    <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-full mb-3">
                                                        <Volume2 className="w-6 h-6 text-gray-400" />
                                                    </div>
                                                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">No Models Found</p>
                                                </div>
                                            ) : (
                                                <>
                                                    <div className="space-y-3">
                                                        <div className="flex items-center justify-between">
                                                            <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                                                Available Voices
                                                            </label>
                                                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-50 dark:bg-rose-900/20 text-rose-600 dark:text-rose-400 font-medium">
                                                                {ttsModels.length} Active
                                                            </span>
                                                        </div>
                                                        <div className="grid grid-cols-2 gap-2">
                                                            {ttsModels.map((p) => (
                                                                <div
                                                                    key={p.name}
                                                                    className="relative flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-xs"
                                                                >
                                                                    {p.name === defaultTtsModel && (
                                                                        <span className="absolute -top-1.5 -right-1.5 px-1.5 py-0.5 rounded-full bg-rose-600 text-white text-[9px] font-bold uppercase tracking-wider shadow-sm">
                                                                            Default
                                                                        </span>
                                                                    )}
                                                                    <div className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                                                                    <span className="font-medium truncate flex-1 text-gray-900 dark:text-gray-100">{p.name}</span>
                                                                    <span className="opacity-60 text-[10px] font-mono shrink-0 text-gray-500 dark:text-gray-400">{p.provider}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>

                                                    <div className="space-y-4 pt-2 border-t border-gray-100 dark:border-gray-700">
                                                        <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                                            Task Assignment
                                                        </label>

                                                        <div className="space-y-2">
                                                            {[
                                                                { key: "slide_lecture", label: "Slide Lecture", desc: "Narration for generated slide lectures" },
                                                                { key: "voiceover", label: "Subtitle Voiceover", desc: "Dubbing for video subtitles" },
                                                                { key: "default", label: "Default Voice", desc: "Fallback for unspecified tasks" },
                                                            ].map(({ key, label, desc }) => (
                                                                <div key={key} className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-4 p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                                                                    <div className="flex flex-col min-w-0">
                                                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</span>
                                                                        <span className="text-[10px] text-gray-400 truncate">{desc}</span>
                                                                    </div>
                                                                    <span className="text-xs font-medium text-rose-600 dark:text-rose-400 px-2 py-1 bg-rose-50 dark:bg-rose-900/20 rounded">
                                                                        {ttsTaskModels[key] || defaultTtsModel}
                                                                    </span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>

                                                    <p className="text-xs text-gray-400 dark:text-gray-500 text-center pt-2">
                                                        Voice assignments are configured in <code className="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-700 font-mono text-[10px]">conf.yaml</code>
                                                    </p>
                                                </>
                                            )}
                                        </div>
                                    </section>
                                </>
                            )}

                            {/* Live2D Tab */}
                            {activeTab === "live2d" && (
                                <section className="space-y-4">
                                    <div className="flex items-center gap-2 text-cyan-600 dark:text-cyan-400">
                                        <User className="w-5 h-5" />
                                        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Live2D Avatar</h3>
                                    </div>

                                    <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
                                        <div className="flex items-center justify-between">
                                            <div className="flex flex-col">
                                                <span className="font-medium text-gray-900 dark:text-gray-100">Show Avatar</span>
                                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                                    Display interactive Live2D avatar on video page
                                                </span>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={handleToggleLive2d}
                                                className={cn(
                                                    "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500/50",
                                                    live2dEnabled ? "bg-cyan-500 border-cyan-500" : "bg-gray-200 dark:bg-gray-700 border-gray-300 dark:border-gray-600"
                                                )}
                                            >
                                                <span
                                                    className={cn(
                                                        "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                                                        live2dEnabled ? "translate-x-5" : "translate-x-1"
                                                    )}
                                                />
                                            </button>
                                        </div>

                                        {live2dEnabled && (
                                            <>
                                                <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                                        Model
                                                    </label>
                                                    <CustomSelect
                                                        value={live2dModelPath}
                                                        onChange={setLive2dModelPath}
                                                        options={
                                                            modelsLoading
                                                                ? [{ value: "", label: "Loading..." }]
                                                                : live2dModels.length === 0
                                                                    ? [{ value: "", label: "No models found" }]
                                                                    : live2dModels.map((model) => ({ value: model.path, label: model.name }))
                                                        }
                                                        disabled={modelsLoading}
                                                        accent="cyan"
                                                    />
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                        Drag to move, resize from corner. Click avatar to interact.
                                                    </p>
                                                </div>

                                                <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-700">
                                                    <div className="flex flex-col">
                                                        <span className="font-medium text-gray-900 dark:text-gray-100">Sync with Video Audio</span>
                                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                                            Avatar lip sync follows video audio
                                                        </span>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={handleToggleLive2dSyncWithVideo}
                                                        className={cn(
                                                            "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500/50",
                                                            live2dSyncWithVideoAudio ? "bg-cyan-500 border-cyan-500" : "bg-gray-200 dark:bg-gray-700 border-gray-300 dark:border-gray-600"
                                                        )}
                                                    >
                                                        <span
                                                            className={cn(
                                                                "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                                                                live2dSyncWithVideoAudio ? "translate-x-5" : "translate-x-1"
                                                            )}
                                                        />
                                                    </button>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </section>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
