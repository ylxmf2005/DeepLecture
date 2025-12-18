"use client";

import { Loader2, FileText, Download } from "lucide-react";
import { useUploadQueueStore } from "@/stores/uploadQueueStore";

interface SubmitSectionProps {
    onSuccess: () => void;
}

export function SubmitSection({ onSuccess }: SubmitSectionProps) {
    const pdfFiles = useUploadQueueStore((s) => s.pdfFiles);
    const videoFiles = useUploadQueueStore((s) => s.videoFiles);
    const pdfCustomName = useUploadQueueStore((s) => s.pdfCustomName);
    const videoCustomName = useUploadQueueStore((s) => s.videoCustomName);
    const setPdfCustomName = useUploadQueueStore((s) => s.setPdfCustomName);
    const setVideoCustomName = useUploadQueueStore((s) => s.setVideoCustomName);
    const submitPdfs = useUploadQueueStore((s) => s.submitPdfs);
    const submitVideos = useUploadQueueStore((s) => s.submitVideos);
    const uploadingPdf = useUploadQueueStore((s) => s.uploadingPdf);
    const uploadingVideo = useUploadQueueStore((s) => s.uploadingVideo);

    const hasPdfs = pdfFiles.length > 0;
    const hasVideos = videoFiles.length > 0;

    if (!hasPdfs && !hasVideos) return null;

    return (
        <div className="mt-6 space-y-4">
            {hasPdfs && (
                <div className="p-4 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
                    <div className="flex items-center gap-2 mb-3">
                        <FileText className="w-4 h-4 text-orange-600 dark:text-orange-400" />
                        <span className="text-sm font-medium text-orange-700 dark:text-orange-300">
                            Upload {pdfFiles.length} PDF{pdfFiles.length > 1 ? "s" : ""}
                        </span>
                    </div>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={pdfCustomName}
                            onChange={(e) => setPdfCustomName(e.target.value)}
                            placeholder="Custom name (optional)"
                            disabled={uploadingPdf}
                            className="flex-1 px-3 py-2 text-sm border border-orange-300 dark:border-orange-700 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:opacity-50"
                        />
                        <button
                            type="button"
                            onClick={() => submitPdfs(onSuccess)}
                            disabled={uploadingPdf || uploadingVideo}
                            className="px-4 py-2 text-sm font-medium text-white bg-orange-600 hover:bg-orange-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {uploadingPdf ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Uploading...
                                </>
                            ) : (
                                "Upload PDFs"
                            )}
                        </button>
                    </div>
                </div>
            )}

            {hasVideos && (
                <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                    <div className="flex items-center gap-2 mb-3">
                        <Download className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                        <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                            Upload {videoFiles.length} Video{videoFiles.length > 1 ? "s" : ""}
                        </span>
                    </div>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={videoCustomName}
                            onChange={(e) => setVideoCustomName(e.target.value)}
                            placeholder="Custom name (optional)"
                            disabled={uploadingVideo}
                            className="flex-1 px-3 py-2 text-sm border border-blue-300 dark:border-blue-700 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
                        />
                        <button
                            type="button"
                            onClick={() => submitVideos(onSuccess)}
                            disabled={uploadingPdf || uploadingVideo}
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {uploadingVideo ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Uploading...
                                </>
                            ) : (
                                "Upload Videos"
                            )}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
