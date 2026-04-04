"use client";

import { useState } from "react";
import { Upload, Link as LinkIcon, AlertCircle, Mic } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUploadQueueStore } from "@/stores/uploadQueueStore";
import { FileDropZone, UploadQueue, SubmitSection, UrlImportForm, RealtimeRecordForm, type UploadTab } from "./upload";

interface VideoUploadProps {
    onUploadSuccess: () => void;
}

export function VideoUpload({ onUploadSuccess }: VideoUploadProps) {
    const [activeTab, setActiveTab] = useState<UploadTab>("local");
    const [isDragging, setIsDragging] = useState(false);

    const error = useUploadQueueStore((s) => s.error);
    const clearError = useUploadQueueStore((s) => s.clearError);

    return (
        <div className="w-full">
            {/* Tab Switcher */}
            <div className="flex gap-2 mb-3">
                <button
                    type="button"
                    onClick={() => setActiveTab("local")}
                    aria-pressed={activeTab === "local"}
                    className={cn(
                        "inline-flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-sm font-medium transition-colors",
                        activeTab === "local"
                            ? "bg-primary/10 text-primary"
                            : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                >
                    <Upload className="w-3.5 h-3.5" />
                    Upload
                </button>
                <button
                    type="button"
                    onClick={() => setActiveTab("url")}
                    aria-pressed={activeTab === "url"}
                    className={cn(
                        "inline-flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-sm font-medium transition-colors",
                        activeTab === "url"
                            ? "bg-primary/10 text-primary"
                            : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                >
                    <LinkIcon className="w-3.5 h-3.5" />
                    URL
                </button>
                <button
                    type="button"
                    onClick={() => setActiveTab("record")}
                    aria-pressed={activeTab === "record"}
                    className={cn(
                        "inline-flex items-center gap-1.5 py-1.5 px-3 rounded-lg text-sm font-medium transition-colors",
                        activeTab === "record"
                            ? "bg-primary/10 text-primary"
                            : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                >
                    <Mic className="w-3.5 h-3.5" />
                    Record
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
            ) : activeTab === "url" ? (
                <UrlImportForm onSuccess={onUploadSuccess} />
            ) : (
                <RealtimeRecordForm onSuccess={onUploadSuccess} />
            )}
        </div>
    );
}
