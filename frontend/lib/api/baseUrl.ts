const DEFAULT_API_PORT = process.env.NEXT_PUBLIC_API_PORT || "11393";

function trimTrailingSlash(url: string): string {
    return url.endsWith("/") ? url.slice(0, -1) : url;
}

function browserApiBaseUrl(): string {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:${DEFAULT_API_PORT}`;
}

export function resolveApiBaseUrl(): string {
    const configured = process.env.NEXT_PUBLIC_API_URL;
    if (configured) {
        return trimTrailingSlash(configured);
    }

    if (typeof window !== "undefined") {
        return browserApiBaseUrl();
    }

    return `http://127.0.0.1:${DEFAULT_API_PORT}`;
}

export const API_BASE_URL = resolveApiBaseUrl();
