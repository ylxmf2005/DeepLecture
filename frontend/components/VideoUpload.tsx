"use client";

import { useState, useRef } from "react";
import { Upload, Loader2, Link as LinkIcon, Download, X, GripVertical, FileText } from "lucide-react";
import { uploadContent, importVideoFromUrl, api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface VideoUploadProps {
    onUploadSuccess: () => void;
}

type UploadTab = "local" | "url";

interface PdfFile {
    id: string;
    file: File;
    name: string;
    size: number;
    pageCount?: number;
}

interface VideoFile {
    id: string;
    file: File;
    name: string;
    size: number;
    duration?: number;
}

export function VideoUpload({ onUploadSuccess }: VideoUploadProps) {
    const [activeTab, setActiveTab] = useState<UploadTab>("local");
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // URL Import State
    const [url, setUrl] = useState("");
    const [customName, setCustomName] = useState("");

    // Multi-PDF upload state
    const [pdfFiles, setPdfFiles] = useState<PdfFile[]>([]);
    const [pdfCustomName, setPdfCustomName] = useState("");
    const [pdfDraggedIndex, setPdfDraggedIndex] = useState<number | null>(null);

    // Multi-Video upload state
    const [videoFiles, setVideoFiles] = useState<VideoFile[]>([]);
    const [videoCustomName, setVideoCustomName] = useState("");
    const [videoDraggedIndex, setVideoDraggedIndex] = useState<number | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const dragCounterRef = useRef(0);

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

    const ALLOWED_VIDEO_EXTS = ["mp4", "webm", "mov"];
    const ALLOWED_VIDEO_MIMES = ["video/mp4", "video/webm", "video/quicktime"];

    const isAllowedVideo = (file: File) => {
        const ext = file.name.split(".").pop()?.toLowerCase() || "";
        return ALLOWED_VIDEO_MIMES.includes(file.type) || ALLOWED_VIDEO_EXTS.includes(ext);
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        dragCounterRef.current = 0;
        setIsDragging(false);
        const files = Array.from(e.dataTransfer.files);

        // Separate PDFs and videos
        const pdfFiles = files.filter(f => f.type === 'application/pdf');
        const videoFiles = files.filter(isAllowedVideo);

        if (pdfFiles.length > 0) {
            handlePdfFilesAdded(pdfFiles);
        }
        if (videoFiles.length > 0) {
            handleVideoFilesAdded(videoFiles);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const files = Array.from(e.target.files);
            const pdfFiles = files.filter(f => f.type === 'application/pdf');
            const videoFiles = files.filter(isAllowedVideo);

            if (pdfFiles.length > 0) {
                // Any PDFs selected - add to staging area
                handlePdfFilesAdded(pdfFiles);
            }
            if (videoFiles.length > 0) {
                // Any videos selected - add to staging area
                handleVideoFilesAdded(videoFiles);
            }
        }
    };

    const handlePdfFilesAdded = (files: File[]) => {
        const newPdfFiles: PdfFile[] = files.map(file => ({
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            file,
            name: file.name,
            size: file.size,
        }));

        setPdfFiles(prev => [...prev, ...newPdfFiles]);
        setError(null);

        // Set default name from first file if not already set
        if (!pdfCustomName && newPdfFiles.length > 0) {
            const firstName = newPdfFiles[0].name.replace(/\.pdf$/i, '');
            setPdfCustomName(firstName);
        }
    };

    const handleVideoFilesAdded = (files: File[]) => {
        const newVideoFiles: VideoFile[] = files.map(file => ({
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            file,
            name: file.name,
            size: file.size,
        }));

        setVideoFiles(prev => [...prev, ...newVideoFiles]);
        setError(null);

        // Set default name from first file if not already set
        if (!videoCustomName && newVideoFiles.length > 0) {
            const firstName = newVideoFiles[0].name.replace(/\.(mp4|webm|mov)$/i, '');
            setVideoCustomName(firstName);
        }
    };

    const handleRemovePdf = (id: string) => {
        setPdfFiles(prev => {
            const newFiles = prev.filter(pdf => pdf.id !== id);
            // Clear custom name if list becomes empty
            if (newFiles.length === 0) {
                setPdfCustomName("");
            }
            return newFiles;
        });
    };

    const handleRemoveVideo = (id: string) => {
        setVideoFiles(prev => {
            const newFiles = prev.filter(video => video.id !== id);
            // Clear custom name if list becomes empty
            if (newFiles.length === 0) {
                setVideoCustomName("");
            }
            return newFiles;
        });
    };

    const handlePdfDragStart = (index: number) => {
        setPdfDraggedIndex(index);
    };

    const handlePdfDragOver = (e: React.DragEvent) => {
        e.preventDefault();
    };

    const handlePdfDragEnter = (index: number) => {
        if (pdfDraggedIndex === null || pdfDraggedIndex === index) return;

        const newFiles = [...pdfFiles];
        const draggedFile = newFiles[pdfDraggedIndex];
        newFiles.splice(pdfDraggedIndex, 1);
        newFiles.splice(index, 0, draggedFile);

        setPdfFiles(newFiles);
        setPdfDraggedIndex(index);
    };

    const handlePdfDragEnd = () => {
        setPdfDraggedIndex(null);
    };

    const handleVideoDragStart = (index: number) => {
        setVideoDraggedIndex(index);
    };

    const handleVideoDragOver = (e: React.DragEvent) => {
        e.preventDefault();
    };

    const handleVideoDragEnter = (index: number) => {
        if (videoDraggedIndex === null || videoDraggedIndex === index) return;

        const newFiles = [...videoFiles];
        const draggedFile = newFiles[videoDraggedIndex];
        newFiles.splice(videoDraggedIndex, 1);
        newFiles.splice(index, 0, draggedFile);

        setVideoFiles(newFiles);
        setVideoDraggedIndex(index);
    };

    const handleVideoDragEnd = () => {
        setVideoDraggedIndex(null);
    };

    const handleSubmitPdfs = async () => {
        if (pdfFiles.length === 0) return;

        setIsUploading(true);
        setError(null);

        try {
            const formData = new FormData();
            pdfFiles.forEach((pdfFile, index) => {
                formData.append('pdfs', pdfFile.file);
            });
            formData.append('custom_name', pdfCustomName || pdfFiles[0].name.replace(/\.pdf$/i, ''));

            await api.post('/content/upload-multiple-pdfs', formData);

            onUploadSuccess();
            setPdfFiles([]);
            setPdfCustomName('');
        } catch (err) {
            console.error(err);
            setError("Failed to upload PDFs. Please try again.");
        } finally {
            setIsUploading(false);
        }
    };

    const handleSubmitVideos = async () => {
        if (videoFiles.length === 0) return;

        setIsUploading(true);
        setError(null);

        try {
            const formData = new FormData();
            videoFiles.forEach((videoFile, index) => {
                formData.append('videos', videoFile.file);
            });
            formData.append('custom_name', videoCustomName || videoFiles[0].name.replace(/\.(mp4|webm|mov)$/i, ''));

            await api.post('/content/upload-multiple-videos', formData);

            onUploadSuccess();
            setVideoFiles([]);
            setVideoCustomName('');
        } catch (err) {
            console.error(err);
            setError("Failed to upload videos. Please try again.");
        } finally {
            setIsUploading(false);
        }
    };

    const handleLocalUpload = async (file: File) => {
        setIsUploading(true);
        setError(null);

        try {
            await uploadContent(file);
            onUploadSuccess();
        } catch (err) {
            console.error(err);
            setError("Failed to upload file. Please try again.");
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        }
    };

    const handleUrlImport = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!url) return;

        setIsUploading(true);
        setError(null);

        try {
            await importVideoFromUrl(url, customName || undefined);
            onUploadSuccess();
            setUrl("");
            setCustomName("");
        } catch (err) {
            console.error(err);
            setError("Failed to import video. Please check the URL and try again.");
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="w-full max-w-2xl mx-auto mb-8">
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

            {activeTab === "local" ? (
                <>
                    <label
                        htmlFor="file-upload"
                        className={cn(
                            "relative block border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer focus-within:ring-2 focus-within:ring-blue-500 focus-within:ring-offset-2",
                            isDragging
                                ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                                : "border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500",
                            isUploading && "opacity-50 pointer-events-none",
                            (videoFiles.length > 0 || pdfFiles.length > 0) && "p-4"
                        )}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                    >
                        <input
                            id="file-upload"
                            type="file"
                            ref={fileInputRef}
                            className="sr-only"
                            accept="video/*,application/pdf"
                            multiple
                            onChange={handleFileSelect}
                        />

                        <div className="flex flex-col items-center justify-center gap-4">
                            <div className={cn(
                                "bg-blue-100 dark:bg-blue-900/30 rounded-full",
                                (videoFiles.length > 0 || pdfFiles.length > 0) ? "p-2" : "p-4"
                            )}>
                                {isUploading ? (
                                    <Loader2 className={cn(
                                        "text-blue-600 dark:text-blue-400 animate-spin",
                                        (videoFiles.length > 0 || pdfFiles.length > 0) ? "w-5 h-5" : "w-8 h-8"
                                    )} />
                                ) : (
                                    <Upload className={cn(
                                        "text-blue-600 dark:text-blue-400",
                                        (videoFiles.length > 0 || pdfFiles.length > 0) ? "w-5 h-5" : "w-8 h-8"
                                    )} />
                                )}
                            </div>

                            <div className="space-y-1">
                                <h3 className={cn(
                                    "font-semibold text-foreground",
                                    (videoFiles.length > 0 || pdfFiles.length > 0) ? "text-sm" : "text-lg"
                                )}>
                                    {isUploading
                                        ? "Uploading..."
                                        : (videoFiles.length > 0 || pdfFiles.length > 0)
                                            ? "Add More Files"
                                            : "Upload Video or PDF Slides"
                                    }
                                </h3>
                                <p className="text-xs text-muted-foreground">
                                    {(videoFiles.length > 0 || pdfFiles.length > 0)
                                        ? "Click or drag to add more files"
                                        : "Drag and drop a course video or a PDF slide deck, or click to browse"
                                    }
                                </p>
                            </div>
                        </div>
                    </label>

                    {/* Video Staging Area */}
                    {videoFiles.length > 0 && (
                        <div className="mt-6 space-y-4">
                            <div className="flex items-center justify-between">
                                <h4 className="text-sm font-medium text-foreground">
                                    Selected Videos ({videoFiles.length})
                                </h4>
                                <button
                                    type="button"
                                    onClick={() => setVideoFiles([])}
                                    className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                                >
                                    Clear All
                                </button>
                            </div>

                            <div className="space-y-2">
                                {videoFiles.map((video, index) => (
                                    <div
                                        key={video.id}
                                        draggable
                                        onDragStart={() => handleVideoDragStart(index)}
                                        onDragOver={handleVideoDragOver}
                                        onDragEnter={() => handleVideoDragEnter(index)}
                                        onDragEnd={handleVideoDragEnd}
                                        className={cn(
                                            "flex items-center gap-3 p-3 bg-card border border-border rounded-lg transition-all cursor-move",
                                            videoDraggedIndex === index && "opacity-50",
                                            "hover:border-blue-500/70 hover:bg-blue-500/10"
                                        )}
                                    >
                                        <GripVertical className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                        <Upload className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-foreground truncate">
                                                {video.name}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {(video.size / 1024 / 1024).toFixed(2)} MB
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => handleRemoveVideo(video.id)}
                                            className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                                        >
                                            <X className="w-4 h-4 text-red-600 dark:text-red-400" />
                                        </button>
                                    </div>
                                ))}
                            </div>

                            <div className="space-y-3 pt-2">
                                <div className="space-y-2">
                                    <label htmlFor="video-name" className="text-sm font-medium text-foreground">
                                        Merged Video Name
                                    </label>
                                    <input
                                        id="video-name"
                                        type="text"
                                        value={videoCustomName}
                                        onChange={(e) => setVideoCustomName(e.target.value)}
                                        placeholder="Enter custom name"
                                        className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                <button
                                    type="button"
                                    onClick={handleSubmitVideos}
                                    disabled={isUploading || videoFiles.length === 0}
                                    className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    {isUploading ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Merging and Uploading...
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="w-4 h-4" />
                                            Upload {videoFiles.length} Video{videoFiles.length > 1 ? 's' : ''}
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* PDF Staging Area */}
                    {pdfFiles.length > 0 && (
                        <div className="mt-6 space-y-4">
                            <div className="flex items-center justify-between">
                                <h4 className="text-sm font-medium text-foreground">
                                    Selected PDFs ({pdfFiles.length})
                                </h4>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setPdfFiles([]);
                                        setPdfCustomName("");
                                    }}
                                    className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                                >
                                    Clear All
                                </button>
                            </div>

                            <div className="space-y-2">
                                {pdfFiles.map((pdf, index) => (
                                    <div
                                        key={pdf.id}
                                        draggable
                                        onDragStart={() => handlePdfDragStart(index)}
                                        onDragOver={handlePdfDragOver}
                                        onDragEnter={() => handlePdfDragEnter(index)}
                                        onDragEnd={handlePdfDragEnd}
                                        className={cn(
                                            "flex items-center gap-3 p-3 bg-card border border-border rounded-lg transition-all cursor-move",
                                            pdfDraggedIndex === index && "opacity-50",
                                            "hover:border-blue-500/70 hover:bg-blue-500/10"
                                        )}
                                    >
                                        <GripVertical className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                        <FileText className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-foreground truncate">
                                                {pdf.name}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {(pdf.size / 1024 / 1024).toFixed(2)} MB
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => handleRemovePdf(pdf.id)}
                                            className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                                        >
                                            <X className="w-4 h-4 text-red-600 dark:text-red-400" />
                                        </button>
                                    </div>
                                ))}
                            </div>

                            <div className="space-y-3 pt-2">
                                <div className="space-y-2">
                                    <label htmlFor="pdf-name" className="text-sm font-medium text-foreground">
                                        Final Name
                                    </label>
                                    <input
                                        id="pdf-name"
                                        type="text"
                                        value={pdfCustomName}
                                        onChange={(e) => setPdfCustomName(e.target.value)}
                                        placeholder="Enter custom name"
                                        className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                <button
                                    type="button"
                                    onClick={handleSubmitPdfs}
                                    disabled={isUploading || pdfFiles.length === 0}
                                    className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    {isUploading ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Merging and Uploading...
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="w-4 h-4" />
                                            Upload {pdfFiles.length} PDF{pdfFiles.length > 1 ? 's' : ''}
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    )}
                </>
            ) : (
                <div className="bg-card border border-border rounded-lg p-6">
                    <form onSubmit={handleUrlImport} className="space-y-4">
                        <div className="space-y-2">
                            <label htmlFor="url" className="text-sm font-medium text-foreground">
                                Video URL (Bilibili / YouTube)
                            </label>
                            <input
                                id="url"
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://www.bilibili.com/video/..."
                                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                                required
                            />
                        </div>

                        <div className="space-y-2">
                            <label htmlFor="name" className="text-sm font-medium text-foreground">
                                Custom Name (Optional)
                            </label>
                            <input
                                id="name"
                                type="text"
                                value={customName}
                                onChange={(e) => setCustomName(e.target.value)}
                                placeholder="My Course Video"
                                className="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={isUploading || !url}
                            className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {isUploading ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Importing...
                                </>
                            ) : (
                                <>
                                    <Download className="w-4 h-4" />
                                    Import Video
                                </>
                            )}
                        </button>
                    </form>
                </div>
            )}

            {error && (
                <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
                    {error}
                </div>
            )}
        </div>
    );
}
