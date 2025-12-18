/**
 * Security utilities for XSS prevention and input sanitization.
 */

/**
 * Allowed URL protocols for safe link rendering.
 */
const SAFE_URL_PROTOCOLS = ["http:", "https:", "mailto:", "tel:"];

/**
 * Validates a URL to prevent javascript: and other dangerous protocols.
 * Returns the URL if safe, otherwise returns undefined.
 */
export function sanitizeUrl(url: string | undefined): string | undefined {
    if (!url) return undefined;

    // Handle relative URLs (safe)
    if (url.startsWith("/") || url.startsWith("#") || url.startsWith(".")) {
        return url;
    }

    try {
        const parsed = new URL(url, "https://placeholder.local");
        if (SAFE_URL_PROTOCOLS.includes(parsed.protocol)) {
            return url;
        }
    } catch {
        // Invalid URL - reject
    }

    return undefined;
}

/**
 * Validates that a URL uses a safe protocol for links.
 */
export function isSafeUrl(url: string | undefined): boolean {
    return sanitizeUrl(url) !== undefined;
}

/**
 * Escapes HTML special characters to prevent XSS.
 * Use this only when absolutely necessary - prefer React's built-in escaping.
 */
export function escapeHtml(text: string): string {
    const htmlEscapes: Record<string, string> = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    };
    return text.replace(/[&<>"']/g, (char) => htmlEscapes[char] ?? char);
}

/**
 * Strips all HTML tags from a string.
 * Useful for displaying user content as plain text.
 */
export function stripHtml(html: string): string {
    return html.replace(/<[^>]*>/g, "");
}

/**
 * Validates that a string contains only safe characters for use in attributes.
 * Allows alphanumeric, hyphens, underscores, and periods.
 */
export function isSafeAttributeValue(value: string): boolean {
    return /^[\w.-]+$/.test(value);
}

/**
 * Creates a safe ID from a potentially unsafe string.
 * Removes or replaces characters that could cause issues.
 */
export function createSafeId(input: string): string {
    return input
        .toLowerCase()
        .replace(/[^a-z0-9-_]/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, 64);
}
