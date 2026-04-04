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
                "border-2 border-dashed rounded-lg px-6 py-4 text-center transition-all duration-200 cursor-pointer",
                isDragging
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/40 hover:bg-muted/50",
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
            <div className="flex items-center justify-center gap-3">
                <Upload className="w-5 h-5 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">Drop files</span>
                    {" "}or click to browse
                    <span className="hidden sm:inline"> &mdash; MP4, WebM, MOV, PDF</span>
                </p>
            </div>
        </div>
    );
}
