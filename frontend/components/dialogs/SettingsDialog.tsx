"use client";

import { X, Settings, Bell, PlayCircle, Zap, Cpu, User, FileText, RotateCcw } from "lucide-react";
import { useEffect, useState, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import type { ContentItem } from "@/lib/api";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { useConfirmDialog } from "@/contexts/ConfirmDialogContext";
import {
    GeneralTab,
    NotificationsTab,
    PlayerTab,
    FunctionsTab,
    ModelTab,
    Live2DTab,
    PromptTab,
} from "./settings";
import { ScopeSwitcher } from "./settings/ScopeSwitcher";
import {
    useSettingsScope,
    useHasVideoScope,
    useOverrideCount,
    type SettingsScope,
} from "./settings/useSettingsScope";
import type { TabId, TabDefinition } from "./settings";

export interface SettingsDialogProps {
    isOpen: boolean;
    onClose: () => void;
    video?: ContentItem;
    /** Open directly in video scope (when opened from per-video settings button) */
    initialScope?: SettingsScope;
}

const TABS: TabDefinition[] = [
    { id: "general", label: "General", icon: Settings },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "player", label: "Player", icon: PlayCircle },
    { id: "functions", label: "Functions", icon: Zap },
    { id: "model", label: "Model", icon: Cpu },
    { id: "prompt", label: "Prompt", icon: FileText },
    { id: "live2d", label: "Live2D", icon: User },
];

export function SettingsDialog({ isOpen, onClose, video, initialScope }: SettingsDialogProps) {
    const dialogRef = useRef<HTMLDivElement>(null);
    const dialogA11yProps = useFocusTrap({
        isOpen,
        onClose,
        containerRef: dialogRef,
    });
    const { confirm } = useConfirmDialog();

    const [activeTab, setActiveTab] = useState<TabId>("general");
    const hasVideoScope = useHasVideoScope();
    const overrideCount = useOverrideCount();
    const [scope, setScope] = useState<SettingsScope>(initialScope ?? "global");

    // Reset scope when dialog opens with initialScope
    useEffect(() => {
        if (isOpen && initialScope) {
            setScope(initialScope);
        }
    }, [isOpen, initialScope]);

    // If no video scope available, force global
    useEffect(() => {
        if (!hasVideoScope && scope === "video") {
            setScope("global");
        }
    }, [hasVideoScope, scope]);

    const settings = useSettingsScope(scope);

    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        }
        return () => {
            document.body.style.overflow = "unset";
        };
    }, [isOpen]);

    const handleResetAllOverrides = useCallback(async () => {
        const confirmed = await confirm({
            title: "Reset All Video Overrides",
            message: "Remove all per-video overrides? This video will use your global settings.",
            confirmLabel: "Reset All",
            variant: "danger",
        });
        if (confirmed) {
            await settings.clearAllOverrides();
        }
    }, [confirm, settings]);

    if (!isOpen) return null;

    const isVideoScope = scope === "video";

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div
                ref={dialogRef}
                {...dialogA11yProps}
                aria-labelledby="settings-dialog-title"
                className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
                    <div className="flex items-center gap-4">
                        <h2 id="settings-dialog-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                            Settings
                        </h2>
                        <ScopeSwitcher
                            scope={scope}
                            onChange={setScope}
                            hasVideoScope={hasVideoScope}
                            overrideCount={overrideCount}
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        {isVideoScope && overrideCount > 0 && (
                            <button
                                type="button"
                                onClick={handleResetAllOverrides}
                                className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 flex items-center gap-1 px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                            >
                                <RotateCcw className="w-3 h-3" />
                                Reset All
                            </button>
                        )}
                        <button
                            onClick={onClose}
                            aria-label="Close settings dialog"
                            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Main content area with tabs */}
                <div className="flex flex-1 overflow-hidden">
                    {/* Sidebar navigation */}
                    <div className="w-48 bg-gray-50 dark:bg-gray-900/50 border-r border-gray-200 dark:border-gray-800">
                        <nav className="p-2 space-y-1">
                            {TABS.map((tab) => {
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
                            {activeTab === "general" && <GeneralTab video={video} scope={scope} settings={settings} />}
                            {activeTab === "notifications" && <NotificationsTab video={video} scope={scope} settings={settings} />}
                            {activeTab === "player" && <PlayerTab video={video} scope={scope} settings={settings} />}
                            {activeTab === "functions" && <FunctionsTab video={video} scope={scope} settings={settings} />}
                            {activeTab === "model" && <ModelTab video={video} scope={scope} settings={settings} />}
                            {activeTab === "live2d" && <Live2DTab video={video} scope={scope} settings={settings} />}
                            {activeTab === "prompt" && <PromptTab video={video} scope={scope} settings={settings} />}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
