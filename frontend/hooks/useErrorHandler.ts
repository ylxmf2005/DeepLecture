"use client";

import { useState, useCallback } from "react";

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

            // Auto-remove after 5 seconds for non-errors
            if (type !== "error") {
                setTimeout(() => {
                    setErrors((prev) => prev.filter((e) => e.id !== newError.id));
                }, 5000);
            }
        },
        []
    );

    const removeError = useCallback((id: string) => {
        setErrors((prev) => prev.filter((e) => e.id !== id));
    }, []);

    const clearErrors = useCallback(() => {
        setErrors([]);
    }, []);

    const handleApiError = useCallback(
        (error: unknown, fallbackMessage = "An unexpected error occurred") => {
            let message = fallbackMessage;
            let details: string | undefined;

            if (error instanceof Error) {
                message = error.message || fallbackMessage;
                details = error.stack;
            } else if (typeof error === "object" && error !== null) {
                const errorObj = error as Record<string, unknown>;
                if (typeof errorObj.message === "string") {
                    message = errorObj.message;
                }
                if (typeof errorObj.detail === "string") {
                    message = errorObj.detail;
                }
            }

            console.error("API Error:", error);
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
