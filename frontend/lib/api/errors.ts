/**
 * API Error types and utilities for structured error handling.
 */

import axios from "axios";
import { getErrorMessage, getErrorStatus } from "@/lib/utils/errorUtils";

export type APIErrorCode =
    | "NETWORK_ERROR"
    | "TIMEOUT"
    | "CANCELLED"
    | "BAD_REQUEST"
    | "UNAUTHORIZED"
    | "FORBIDDEN"
    | "NOT_FOUND"
    | "SERVER_ERROR"
    | "UNKNOWN";

export interface APIErrorContext {
    url?: string;
    method?: string;
    data?: unknown;
}

/**
 * Structured API error with classification and context.
 */
export class APIError extends Error {
    readonly code: APIErrorCode;
    readonly status?: number;
    readonly context?: APIErrorContext;
    readonly originalError?: unknown;

    constructor(
        message: string,
        code: APIErrorCode,
        options?: {
            status?: number;
            context?: APIErrorContext;
            originalError?: unknown;
        }
    ) {
        super(message);
        this.name = "APIError";
        this.code = code;
        this.status = options?.status;
        this.context = options?.context;
        this.originalError = options?.originalError;
    }

    /**
     * Check if this is a network-related error (no response from server).
     */
    isNetworkError(): boolean {
        return this.code === "NETWORK_ERROR" || this.code === "TIMEOUT";
    }

    /**
     * Check if this is a client error (4xx).
     */
    isClientError(): boolean {
        return this.status !== undefined && this.status >= 400 && this.status < 500;
    }

    /**
     * Check if this is a server error (5xx).
     */
    isServerError(): boolean {
        return this.status !== undefined && this.status >= 500;
    }

    /**
     * Check if the request was cancelled.
     */
    isCancelled(): boolean {
        return this.code === "CANCELLED";
    }
}

/**
 * Classify error code based on Axios error or HTTP status.
 */
function classifyErrorCode(error: unknown): { code: APIErrorCode; status?: number } {
    if (axios.isCancel(error)) {
        return { code: "CANCELLED" };
    }

    if (axios.isAxiosError(error)) {
        if (error.code === "ECONNABORTED" || error.message?.includes("timeout")) {
            return { code: "TIMEOUT" };
        }

        if (!error.response) {
            return { code: "NETWORK_ERROR" };
        }

        const status = error.response.status;
        switch (status) {
            case 400:
                return { code: "BAD_REQUEST", status };
            case 401:
                return { code: "UNAUTHORIZED", status };
            case 403:
                return { code: "FORBIDDEN", status };
            case 404:
                return { code: "NOT_FOUND", status };
            default:
                if (status >= 500) {
                    return { code: "SERVER_ERROR", status };
                }
                return { code: "UNKNOWN", status };
        }
    }

    // Check if it has status from errorUtils
    const status = getErrorStatus(error);
    if (status !== undefined) {
        if (status >= 400 && status < 500) {
            return { code: "BAD_REQUEST", status };
        }
        if (status >= 500) {
            return { code: "SERVER_ERROR", status };
        }
    }

    return { code: "UNKNOWN" };
}

/**
 * Wrap any error into a structured APIError.
 * Preserves original error for debugging.
 */
export function wrapAPIError(error: unknown, context?: APIErrorContext): APIError {
    // Already an APIError, just return it
    if (error instanceof APIError) {
        return error;
    }

    const { code, status } = classifyErrorCode(error);
    const message = getErrorMessage(error, getDefaultMessage(code));

    return new APIError(message, code, {
        status,
        context,
        originalError: error,
    });
}

/**
 * Get a user-friendly default message for error codes.
 */
function getDefaultMessage(code: APIErrorCode): string {
    switch (code) {
        case "NETWORK_ERROR":
            return "Unable to connect to the server. Please check your internet connection.";
        case "TIMEOUT":
            return "The request timed out. Please try again.";
        case "CANCELLED":
            return "The request was cancelled.";
        case "BAD_REQUEST":
            return "Invalid request. Please check your input.";
        case "UNAUTHORIZED":
            return "You are not authorized. Please log in.";
        case "FORBIDDEN":
            return "You do not have permission to perform this action.";
        case "NOT_FOUND":
            return "The requested resource was not found.";
        case "SERVER_ERROR":
            return "A server error occurred. Please try again later.";
        default:
            return "An unexpected error occurred.";
    }
}

/**
 * Type guard to check if error is an APIError.
 */
export function isAPIError(error: unknown): error is APIError {
    return error instanceof APIError;
}
