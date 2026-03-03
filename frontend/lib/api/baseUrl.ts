const DEFAULT_API_PORT = process.env.NEXT_PUBLIC_API_PORT || "11393";
const DEFAULT_API_BASE_URL = `http://localhost:${DEFAULT_API_PORT}`;

function trimTrailingSlash(url: string): string {
    return url.endsWith("/") ? url.slice(0, -1) : url;
}

export function resolveApiBaseUrl(): string {
    const configured = process.env.NEXT_PUBLIC_API_URL;
    if (configured) {
        return trimTrailingSlash(configured);
    }

    // Keep SSR/CSR deterministic to avoid hydration mismatches.
    return DEFAULT_API_BASE_URL;
}

export const API_BASE_URL = resolveApiBaseUrl();
