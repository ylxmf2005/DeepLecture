"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { logger } from "@/shared/infrastructure";
import { toError, getErrorMessage } from "@/lib/utils/errorUtils";

const log = logger.scope("ErrorHandler");

/** Auto-dismiss timeout for non-error notifications */
const AUTO_DISMISS_MS = 5000;

export interface AppError {
    id: string;
    message: string;
    type: "error" | "warning" | "info" | "success";
    timestamp: number;
    details?: string;
}

interface UseErrorHandlerReturn {
    errors: AppError[];
    addError: (message: string, type?: AppError["type"], details?: string) => void;
    removeError: (id: string) => void;
    clearErrors: () => void;
    handleApiError: (error: unknown, fallbackMessage?: string) => void;
}

/**
 * Central error handling hook for the application.
 * Provides a unified way to manage and display errors/notifications.
 */
export function useErrorHandler(): UseErrorHandlerReturn {
    const [errors, setErrors] = useState<AppError[]>([]);
    // Track timeout IDs for cleanup on unmount or manual dismiss
    const timeoutMapRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

    // Cleanup all pending timeouts on unmount
    useEffect(() => {
        const timeoutMap = timeoutMapRef.current;
        return () => {
            timeoutMap.forEach(clearTimeout);
            timeoutMap.clear();
        };
    }, []);

    const addError = useCallback(
        (message: string, type: AppError["type"] = "error", details?: string) => {
            const newError: AppError = {
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                message,
                type,
                timestamp: Date.now(),
                details,
            };

            setErrors((prev) => [...prev, newError]);

            // Auto-remove after timeout for non-errors, with proper cleanup tracking
            if (type !== "error") {
                const timeoutId = setTimeout(() => {
                    timeoutMapRef.current.delete(newError.id);
                    setErrors((prev) => prev.filter((e) => e.id !== newError.id));
                }, AUTO_DISMISS_MS);
                timeoutMapRef.current.set(newError.id, timeoutId);
            }
        },
        []
    );

    const removeError = useCallback((id: string) => {
        // Clear any pending auto-dismiss timeout for this error
        const timeoutId = timeoutMapRef.current.get(id);
        if (timeoutId) {
            clearTimeout(timeoutId);
            timeoutMapRef.current.delete(id);
        }
        setErrors((prev) => prev.filter((e) => e.id !== id));
    }, []);

    const clearErrors = useCallback(() => {
        // Clear all pending timeouts
        timeoutMapRef.current.forEach(clearTimeout);
        timeoutMapRef.current.clear();
        setErrors([]);
    }, []);

    const handleApiError = useCallback(
        (error: unknown, fallbackMessage = "An unexpected error occurred") => {
            const errorObj = toError(error);
            const message = getErrorMessage(error, fallbackMessage);
            const details = errorObj.stack;

            log.error("API Error", errorObj, { fallbackMessage, details });
            addError(message, "error", details);
        },
        [addError]
    );

    return {
        errors,
        addError,
        removeError,
        clearErrors,
        handleApiError,
    };
}
