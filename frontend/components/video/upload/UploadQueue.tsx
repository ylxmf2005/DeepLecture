"use client";

import { X, GripVertical, FileText, Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUploadQueueStore } from "@/stores/uploadQueueStore";

interface UploadQueueProps {
    type: "pdf" | "video";
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadQueue({ type }: UploadQueueProps) {
    const pdfFiles = useUploadQueueStore((s) => s.pdfFiles);
    const videoFiles = useUploadQueueStore((s) => s.videoFiles);
    const removePdfFile = useUploadQueueStore((s) => s.removePdfFile);
    const removeVideoFile = useUploadQueueStore((s) => s.removeVideoFile);
    const reorderPdfFiles = useUploadQueueStore((s) => s.reorderPdfFiles);
    const reorderVideoFiles = useUploadQueueStore((s) => s.reorderVideoFiles);
    const uploadingPdf = useUploadQueueStore((s) => s.uploadingPdf);
    const uploadingVideo = useUploadQueueStore((s) => s.uploadingVideo);

    const files = type === "pdf" ? pdfFiles : videoFiles;
    const removeFile = type === "pdf" ? removePdfFile : removeVideoFile;
    const reorderFiles = type === "pdf" ? reorderPdfFiles : reorderVideoFiles;
    const isUploading = type === "pdf" ? uploadingPdf : uploadingVideo;

    if (files.length === 0) return null;

    const handleDragStart = (e: React.DragEvent, index: number) => {
        e.dataTransfer.setData("text/plain", String(index));
        e.dataTransfer.effectAllowed = "move";
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
    };

    const handleDrop = (e: React.DragEvent, targetIndex: number) => {
        e.preventDefault();
        const sourceIndex = parseInt(e.dataTransfer.getData("text/plain"), 10);
        if (!isNaN(sourceIndex) && sourceIndex !== targetIndex) {
            reorderFiles(sourceIndex, targetIndex);
        }
    };

    return (
        <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                {type === "pdf" ? <FileText className="w-4 h-4" /> : <Download className="w-4 h-4" />}
                {type === "pdf" ? "PDF Files" : "Video Files"} ({files.length})
            </h3>
            <div className="space-y-2">
                {files.map((file, index) => (
                    <div
                        key={file.id}
                        draggable={!isUploading}
                        onDragStart={(e) => handleDragStart(e, index)}
                        onDragOver={handleDragOver}
                        onDrop={(e) => handleDrop(e, index)}
                        className={cn(
                            "flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700",
                            !isUploading && "cursor-grab active:cursor-grabbing"
                        )}
                    >
                        <GripVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate">
                                {file.name}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {formatFileSize(file.size)}
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={() => removeFile(file.id)}
                            disabled={isUploading}
                            className="p-1 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
                            aria-label={`Remove ${file.name}`}
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}
