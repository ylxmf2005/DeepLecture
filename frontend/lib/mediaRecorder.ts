export type RecordingExtension = "webm" | "mp4";

export interface RecordingFormat {
    mimeType: string;
    extension: RecordingExtension;
}

const PREFERRED_MIME_TYPES = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
] as const;

const AUDIO_EXTENSION_PATTERN = /\.(webm|mp4|m4a|mp3|wav|aac|opus)$/i;

function formatTimestampUTC(date: Date): string {
    const yyyy = date.getUTCFullYear();
    const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(date.getUTCDate()).padStart(2, "0");
    const hh = String(date.getUTCHours()).padStart(2, "0");
    const min = String(date.getUTCMinutes()).padStart(2, "0");
    const ss = String(date.getUTCSeconds()).padStart(2, "0");
    return `${yyyy}${mm}${dd}_${hh}${min}${ss}`;
}

function sanitizeBaseName(value: string): string {
    return value
        .trim()
        .replace(AUDIO_EXTENSION_PATTERN, "")
        .replace(/[\\/:*?"<>|]/g, "_")
        .replace(/\s+/g, " ");
}

export function selectRecordingFormat(): RecordingFormat {
    if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") {
        return { mimeType: "", extension: "webm" };
    }

    for (const mimeType of PREFERRED_MIME_TYPES) {
        if (MediaRecorder.isTypeSupported(mimeType)) {
            return {
                mimeType,
                extension: mimeType.includes("mp4") ? "mp4" : "webm",
            };
        }
    }

    return { mimeType: "", extension: "webm" };
}

export function extensionFromMimeType(
    mimeType: string | undefined,
    fallback: RecordingExtension = "webm"
): RecordingExtension {
    if (!mimeType) return fallback;
    return mimeType.includes("mp4") ? "mp4" : "webm";
}

export function buildRecordingFilename(
    customName: string,
    extension: RecordingExtension,
    now: Date = new Date()
): string {
    const baseName = sanitizeBaseName(customName);
    if (baseName) {
        return `${baseName}.${extension}`;
    }
    return `recording_${formatTimestampUTC(now)}.${extension}`;
}

export function formatRecordingDuration(durationMs: number): string {
    const clampedMs = Number.isFinite(durationMs) ? Math.max(0, durationMs) : 0;
    const totalSeconds = Math.floor(clampedMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
