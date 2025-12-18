/**
 * Error handling utilities for consistent error coercion and handling patterns.
 */

/**
 * Coerce any unknown value to an Error instance.
 * Useful for catch blocks where error type is unknown.
 *
 * @example
 * try { ... } catch (err) {
 *   log.error("Failed", toError(err));
 * }
 */
export function toError(err: unknown): Error {
    if (err instanceof Error) {
        return err;
    }
    if (typeof err === "string") {
        return new Error(err);
    }
    if (typeof err === "object" && err !== null) {
        const obj = err as Record<string, unknown>;
        if (typeof obj.message === "string") {
            return new Error(obj.message);
        }
        if (typeof obj.detail === "string") {
            return new Error(obj.detail);
        }
    }
    return new Error(String(err));
}

/**
 * Extract error message from unknown error value.
 */
export function getErrorMessage(err: unknown, fallback = "An unexpected error occurred"): string {
    if (err instanceof Error) {
        return err.message || fallback;
    }
    if (typeof err === "string") {
        return err || fallback;
    }
    if (typeof err === "object" && err !== null) {
        const obj = err as Record<string, unknown>;
        if (typeof obj.message === "string") {
            return obj.message;
        }
        if (typeof obj.detail === "string") {
            return obj.detail;
        }
    }
    return fallback;
}

/**
 * Type guard to check if error is an Axios-like error with response.
 */
export function isAxiosError(err: unknown): err is { response?: { status?: number; data?: unknown } } {
    return typeof err === "object" && err !== null && "response" in err;
}

/**
 * Get HTTP status code from error if available.
 */
export function getErrorStatus(err: unknown): number | undefined {
    if (isAxiosError(err)) {
        return err.response?.status;
    }
    return undefined;
}
