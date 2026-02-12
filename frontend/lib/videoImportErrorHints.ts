const COOKIE_UNAVAILABLE_MARKERS = [
    "failed to load cookies",
    "could not find chrome cookies database",
    "could not find local state file",
    "failed to decrypt cookie",
    "failed to decrypt with dpapi",
    "cannot extract cookies from chrome",
];

const YOUTUBE_AUTH_REQUIRED_MARKERS = [
    "sign in to confirm you're not a bot",
    "sign in to confirm you’re not a bot",
    "age-restricted",
    "confirm your age",
    "private video",
    "this video is private",
    "members-only",
    "channel members only",
    "authentication required",
    "login required",
];

function containsAny(text: string, markers: string[]): boolean {
    const lower = text.toLowerCase();
    return markers.some((marker) => lower.includes(marker));
}

export function buildVideoImportErrorHint(errorMessage?: string): string | null {
    const raw = (errorMessage || "").trim();
    if (!raw) return null;

    if (containsAny(raw, COOKIE_UNAVAILABLE_MARKERS)) {
        return "Chrome cookies could not be read. Sign in to YouTube in Chrome, close all Chrome windows, then retry.";
    }

    if (containsAny(raw, YOUTUBE_AUTH_REQUIRED_MARKERS)) {
        return "YouTube requires authentication for this video. Sign in with Chrome and retry, or use exported cookies.txt.";
    }

    return null;
}
