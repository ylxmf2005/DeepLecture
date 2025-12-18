"use client";

import { useRef } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUploadQueueStore } from "@/stores/uploadQueueStore";

interface FileDropZoneProps {
    isDragging: boolean;
    setIsDragging: (dragging: boolean) => void;
}

export function FileDropZone({ isDragging, setIsDragging }: FileDropZoneProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const dragCounterRef = useRef(0);

    const addFiles = useUploadQueueStore((s) => s.addFiles);
    const uploadingPdf = useUploadQueueStore((s) => s.uploadingPdf);
    const uploadingVideo = useUploadQueueStore((s) => s.uploadingVideo);

    const isUploading = uploadingPdf || uploadingVideo;

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
    };

    const handleDragEnter = (e: React.DragEvent) => {
        e.preventDefault();
        dragCounterRef.current++;
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        dragCounterRef.current--;
        if (dragCounterRef.current === 0) {
            setIsDragging(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        dragCounterRef.current = 0;
        setIsDragging(false);
        const files = Array.from(e.dataTransfer.files);
        addFiles(files);
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const files = Array.from(e.target.files);
            addFiles(files);
            // Reset input so the same file can be selected again
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        }
    };

    const handleClick = () => {
        fileInputRef.current?.click();
    };

    return (
        <div
            className={cn(
                "border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 cursor-pointer",
                isDragging
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                    : "border-gray-300 dark:border-gray-700 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800/50",
                isUploading && "pointer-events-none opacity-50"
            )}
            onDragOver={handleDragOver}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleClick}
        >
            <input
                ref={fileInputRef}
                type="file"
                accept="video/*,.pdf,application/pdf"
                multiple
                onChange={handleFileSelect}
                className="hidden"
            />
            <div className="flex flex-col items-center gap-3">
                <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-900/40">
                    <Upload className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                    <p className="font-medium text-gray-700 dark:text-gray-200">
                        Drop files here or click to browse
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Videos (MP4, WebM, MOV) or PDFs
                    </p>
                </div>
            </div>
        </div>
    );
}
