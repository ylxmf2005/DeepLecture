"use client";

import { X, Settings, Bell, PlayCircle, Zap, Cpu, User, FileText } from "lucide-react";
import { useEffect, useState, useRef } from "react";
import { cn } from "@/lib/utils";
import type { ContentItem } from "@/lib/api";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import {
    GeneralTab,
    NotificationsTab,
    PlayerTab,
    FunctionsTab,
    ModelTab,
    Live2DTab,
    PromptTab,
} from "./settings";
import type { TabId, TabDefinition } from "./settings";

export interface SettingsDialogProps {
    isOpen: boolean;
    onClose: () => void;
    video: ContentItem;
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

export function SettingsDialog({ isOpen, onClose, video }: SettingsDialogProps) {
    const dialogRef = useRef<HTMLDivElement>(null);
    const dialogA11yProps = useFocusTrap({
        isOpen,
        onClose,
        containerRef: dialogRef,
    });

    const [activeTab, setActiveTab] = useState<TabId>("general");

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

    if (!isOpen) return null;

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
                    <h2 id="settings-dialog-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        Settings
                    </h2>
                    <button
                        onClick={onClose}
                        aria-label="Close settings dialog"
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
                            {activeTab === "general" && <GeneralTab video={video} />}
                            {activeTab === "notifications" && <NotificationsTab video={video} />}
                            {activeTab === "player" && <PlayerTab video={video} />}
                            {activeTab === "functions" && <FunctionsTab video={video} />}
                            {activeTab === "model" && <ModelTab video={video} />}
                            {activeTab === "live2d" && <Live2DTab video={video} />}
                            {activeTab === "prompt" && <PromptTab video={video} />}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
