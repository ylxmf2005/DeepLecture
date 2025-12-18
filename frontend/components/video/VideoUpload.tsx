"use client";

import { useState } from "react";
import { Upload, Link as LinkIcon, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUploadQueueStore } from "@/stores/uploadQueueStore";
import { FileDropZone, UploadQueue, SubmitSection, UrlImportForm, type UploadTab } from "./upload";

interface VideoUploadProps {
    onUploadSuccess: () => void;
}

export function VideoUpload({ onUploadSuccess }: VideoUploadProps) {
    const [activeTab, setActiveTab] = useState<UploadTab>("local");
    const [isDragging, setIsDragging] = useState(false);

    const error = useUploadQueueStore((s) => s.error);
    const clearError = useUploadQueueStore((s) => s.clearError);

    return (
        <div className="w-full max-w-2xl mx-auto mb-8">
            {/* Tab Switcher */}
            <div className="flex gap-4 mb-4">
                <button
                    type="button"
                    onClick={() => setActiveTab("local")}
                    aria-pressed={activeTab === "local"}
                    className={cn(
                        "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors",
                        activeTab === "local"
                            ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                    )}
                >
                    <div className="flex items-center justify-center gap-2">
                        <Upload className="w-4 h-4" />
                        Local Upload
                    </div>
                </button>
                <button
                    type="button"
                    onClick={() => setActiveTab("url")}
                    aria-pressed={activeTab === "url"}
                    className={cn(
                        "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors",
                        activeTab === "url"
                            ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                    )}
                >
                    <div className="flex items-center justify-center gap-2">
                        <LinkIcon className="w-4 h-4" />
                        Import from URL
                    </div>
                </button>
            </div>

            {/* Error Display */}
            {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                        <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
                    </div>
                    <button
                        type="button"
                        onClick={clearError}
                        className="text-red-500 hover:text-red-700 text-sm"
                    >
                        Dismiss
                    </button>
                </div>
            )}

            {/* Content */}
            {activeTab === "local" ? (
                <>
                    <FileDropZone isDragging={isDragging} setIsDragging={setIsDragging} />
                    <UploadQueue type="video" />
                    <UploadQueue type="pdf" />
                    <SubmitSection onSuccess={onUploadSuccess} />
                </>
            ) : (
                <UrlImportForm onSuccess={onUploadSuccess} />
            )}
        </div>
    );
}
