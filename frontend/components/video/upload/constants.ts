export const ALLOWED_VIDEO_EXTS = ["mp4", "webm", "mov", "avi", "mkv"] as const;
export const ALLOWED_VIDEO_MIMES = ["video/mp4", "video/webm", "video/quicktime", "video/x-msvideo", "video/x-matroska"] as const;

export const isAllowedVideo = (file: File): boolean => {
    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    return (ALLOWED_VIDEO_MIMES as readonly string[]).includes(file.type) ||
        (ALLOWED_VIDEO_EXTS as readonly string[]).includes(ext);
};
