/**
 * Time formatting utilities
 * Consolidated from multiple components to ensure DRY principle
 */

/**
 * Format seconds to HH:MM:SS string
 * @param seconds - Time in seconds
 * @returns Formatted time string (e.g., "00:01:30")
 */
export function formatTime(seconds: number): string {
    const date = new Date(0);
    date.setSeconds(Math.floor(seconds));
    return date.toISOString().substring(11, 19);
}

/**
 * Format seconds to human-readable duration
 * @param seconds - Duration in seconds
 * @returns Human-readable string (e.g., "5 minutes", "30 seconds")
 */
export function formatDuration(seconds: number): string {
    if (seconds < 60) {
        return `${Math.floor(seconds)} second${Math.floor(seconds) !== 1 ? "s" : ""}`;
    }
    const mins = Math.floor(seconds / 60);
    return `${mins} minute${mins !== 1 ? "s" : ""}`;
}

/**
 * Format seconds to SRT timestamp format
 * @param seconds - Time in seconds
 * @returns SRT formatted timestamp (e.g., "00:01:30,500")
 */
export function formatSrtTimestamp(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const millis = Math.round((seconds % 1) * 1000);

    return `${hours.toString().padStart(2, "0")}:${minutes
        .toString()
        .padStart(2, "0")}:${secs.toString().padStart(2, "0")},${millis
        .toString()
        .padStart(3, "0")}`;
}
