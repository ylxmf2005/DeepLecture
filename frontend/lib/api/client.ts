/**
 * API Client - Axios instance with unified response handling
 * Features:
 * - Automatic snake_case ↔ camelCase conversion (via shared transform)
 * - Request cancellation via AbortController
 * - Structured error handling
 */

import axios, { AxiosRequestConfig, CancelTokenSource } from "axios";
import { wrapAPIError } from "./errors";
import { logger } from "@/shared/infrastructure";
import { camelizeKeys, snakifyKeys, unwrapApiResponse } from "./transform";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:11393";

export const api = axios.create({
    baseURL: `${API_BASE_URL}/api`,
});

// Request interceptor: convert outgoing data to snake_case
api.interceptors.request.use(
    (config) => {
        // Convert request body to snake_case
        if (config.data) {
            config.data = snakifyKeys(config.data);
        }
        // Convert query params to snake_case
        if (config.params) {
            config.params = snakifyKeys(config.params);
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor: unwrap envelope and convert to camelCase
api.interceptors.response.use(
    (response) => {
        if (response.data) {
            response.data = unwrapApiResponse(response.data);
        }
        return response;
    },
    (error) => {
        const log = logger.scope("API");
        const context = {
            url: error.config?.url,
            method: error.config?.method?.toUpperCase(),
        };

        const apiError = wrapAPIError(error, context);

        // Log non-cancellation errors (404s are expected for missing resources)
        if (!apiError.isCancelled()) {
            const logContext = {
                code: apiError.code,
                status: apiError.status,
                message: apiError.message,
                ...context,
            };
            if (apiError.code === "NOT_FOUND") {
                log.debug("Resource not found", logContext);
            } else {
                log.warn("API request failed", logContext);
            }
        }

        return Promise.reject(apiError);
    }
);

/**
 * Create a cancel token source for request cancellation.
 * Use with AbortController pattern.
 *
 * @example
 * const source = createCancelToken();
 * api.get('/endpoint', { cancelToken: source.token });
 * // To cancel:
 * source.cancel('Operation cancelled');
 */
export function createCancelToken(): CancelTokenSource {
    return axios.CancelToken.source();
}

/**
 * Check if an error is a cancellation error.
 */
export function isCancel(error: unknown): boolean {
    return axios.isCancel(error);
}

/**
 * Create an AbortController for request cancellation.
 * Preferred over cancel tokens in modern code.
 *
 * @example
 * const controller = new AbortController();
 * api.get('/endpoint', { signal: controller.signal });
 * // To cancel:
 * controller.abort();
 */
export function createAbortController(): AbortController {
    return new AbortController();
}

/**
 * Helper to add abort signal to request config.
 */
export function withAbortSignal<T extends AxiosRequestConfig>(
    config: T,
    signal: AbortSignal
): T {
    return { ...config, signal };
}
