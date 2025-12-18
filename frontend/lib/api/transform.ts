/**
 * API Response Transform Utilities
 *
 * Pure functions for snake_case ↔ camelCase conversion and response envelope unwrapping.
 * Used by both Axios interceptors (client-side) and fetch helpers (server-side).
 */

type PlainObject = Record<string, unknown>;

const UNSAFE_KEYS = new Set(["__proto__", "prototype", "constructor"]);

const toCamel = (s: string): string =>
    s.replace(/([-_][a-z])/gi, ($1) => $1.toUpperCase().replace("-", "").replace("_", ""));

const toSnake = (s: string): string =>
    s.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);

const isPlainObject = (obj: unknown): obj is PlainObject =>
    Object.prototype.toString.call(obj) === "[object Object]";

/**
 * Recursively convert object keys to camelCase.
 * Returns a normal plain object so Next.js RSC can serialize it.
 * Filters unsafe keys to reduce prototype-pollution risk.
 */
export function camelizeKeys(obj: unknown): unknown {
    if (Array.isArray(obj)) {
        return obj.map((v) => camelizeKeys(v));
    }
    if (isPlainObject(obj)) {
        const result: PlainObject = {};
        for (const key of Object.keys(obj)) {
            if (UNSAFE_KEYS.has(key)) continue;
            const nextKey = toCamel(key);
            if (UNSAFE_KEYS.has(nextKey)) continue;
            result[nextKey] = camelizeKeys(obj[key]);
        }
        return result;
    }
    return obj;
}

/**
 * Recursively convert object keys to snake_case.
 * Returns a normal plain object so Next.js RSC can serialize it.
 * Filters unsafe keys to reduce prototype-pollution risk.
 */
export function snakifyKeys(obj: unknown): unknown {
    if (Array.isArray(obj)) {
        return obj.map((v) => snakifyKeys(v));
    }
    if (isPlainObject(obj)) {
        const result: PlainObject = {};
        for (const key of Object.keys(obj)) {
            if (UNSAFE_KEYS.has(key)) continue;
            const nextKey = toSnake(key);
            if (UNSAFE_KEYS.has(nextKey)) continue;
            result[nextKey] = snakifyKeys(obj[key]);
        }
        return result;
    }
    return obj;
}

/**
 * API response envelope structure from backend.
 */
interface ApiEnvelope {
    success: boolean;
    data?: unknown;
    error?: string;
}

function isApiEnvelope(obj: unknown): obj is ApiEnvelope {
    if (!isPlainObject(obj)) return false;
    if (typeof obj.success !== "boolean") return false;
    return "data" in obj || "error" in obj;
}

/**
 * Unwrap API response envelope and convert keys to camelCase.
 * Throws if response indicates failure or data is missing.
 */
export function unwrapApiResponse<T>(raw: unknown): T {
    const camelized = camelizeKeys(raw);

    if (isApiEnvelope(camelized)) {
        if (!camelized.success) {
            throw new Error(camelized.error || "API request failed");
        }
        if (camelized.data === undefined || camelized.data === null) {
            throw new Error("API response missing data");
        }
        return camelized.data as T;
    }

    return camelized as T;
}
