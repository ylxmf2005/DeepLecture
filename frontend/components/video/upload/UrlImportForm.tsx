"use client";

import { useState } from "react";
import { Loader2, Link as LinkIcon } from "lucide-react";
import { useUploadQueueStore } from "@/stores/uploadQueueStore";

interface UrlImportFormProps {
    onSuccess: () => void;
}

export function UrlImportForm({ onSuccess }: UrlImportFormProps) {
    const [url, setUrl] = useState("");
    const [customName, setCustomName] = useState("");

    const importUrl = useUploadQueueStore((s) => s.importUrl);
    const uploadingUrl = useUploadQueueStore((s) => s.uploadingUrl);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!url) return;

        await importUrl(url, customName, () => {
            setUrl("");
            setCustomName("");
            onSuccess();
        });
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label htmlFor="video-url" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Video URL
                </label>
                <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <LinkIcon className="w-4 h-4 text-gray-400" />
                    </div>
                    <input
                        id="video-url"
                        type="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://example.com/video.mp4"
                        disabled={uploadingUrl}
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
                        required
                    />
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Supports YouTube, direct video URLs, and more
                </p>
            </div>

            <div>
                <label htmlFor="custom-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Custom Name (optional)
                </label>
                <input
                    id="custom-name"
                    type="text"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    placeholder="My Video"
                    disabled={uploadingUrl}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
                />
            </div>

            <button
                type="submit"
                disabled={!url || uploadingUrl}
                className="w-full py-2 px-4 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
                {uploadingUrl ? (
                    <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Importing...
                    </>
                ) : (
                    "Import Video"
                )}
            </button>
        </form>
    );
}
