/**
 * Matches timestamps wrapped in square brackets: [MM:SS], [HH:MM:SS], [5:30], [01:23:45]
 * This format is explicitly requested in LLM prompts to avoid false positives
 * like "John 3:16" or IP addresses "127.0.0.1:22".
 */
export const TIMESTAMP_REGEX = /\[(\d{1,3}:\d{2}(?::\d{2})?)\]/g;

export function parseTimestampToSeconds(token: string): number | null {
    // Remove brackets if present (for tokens extracted from regex match)
    const raw = token.replace(/^\[|\]$/g, "").trim();

    // Validate: only digits and colons allowed
    if (!/^\d{1,3}:\d{2}(?::\d{2})?$/.test(raw)) return null;

    const parts = raw.split(":");
    if (parts.length !== 2 && parts.length !== 3) return null;

    const nums = parts.map((p) => Number.parseInt(p, 10));
    if (nums.some((n) => !Number.isFinite(n) || n < 0)) return null;

    if (parts.length === 2) {
        const minutes = nums[0] ?? 0;
        const seconds = nums[1] ?? 0;
        if (seconds > 59) return null;
        return minutes * 60 + seconds;
    }

    const hours = nums[0] ?? 0;
    const minutes = nums[1] ?? 0;
    const seconds = nums[2] ?? 0;
    if (minutes > 59 || seconds > 59) return null;
    return hours * 3600 + minutes * 60 + seconds;
}

export function isSeekHref(href: string | undefined): href is string {
    return typeof href === "string" && href.startsWith("#t=");
}

export function parseSeekHrefSeconds(href: string): number | null {
    if (!isSeekHref(href)) return null;
    const raw = href.slice("#t=".length);
    // Strict validation: only accept pure digits
    if (!/^\d+$/.test(raw)) return null;
    const seconds = Number.parseInt(raw, 10);
    if (!Number.isFinite(seconds) || seconds < 0) return null;
    return seconds;
}
