"use client";

import { createContext, useContext, ReactNode } from "react";
import { useErrorHandler, AppError } from "@/hooks/useErrorHandler";
import { ToastContainer } from "@/components/ui/Toast";

interface ErrorContextValue {
    errors: AppError[];
    addError: (message: string, type?: AppError["type"], details?: string) => void;
    removeError: (id: string) => void;
    clearErrors: () => void;
    handleApiError: (error: unknown, fallbackMessage?: string) => void;
}

const ErrorContext = createContext<ErrorContextValue | null>(null);

interface ErrorProviderProps {
    children: ReactNode;
}

/**
 * Provider component that wraps the app to provide error handling functionality.
 * Includes a ToastContainer for displaying error notifications.
 */
export function ErrorProvider({ children }: ErrorProviderProps) {
    const errorHandler = useErrorHandler();

    return (
        <ErrorContext.Provider value={errorHandler}>
            {children}
            <ToastContainer errors={errorHandler.errors} onDismiss={errorHandler.removeError} />
        </ErrorContext.Provider>
    );
}

/**
 * Hook to access error handling functionality.
 * Must be used within an ErrorProvider.
 */
export function useErrors() {
    const context = useContext(ErrorContext);
    if (!context) {
        throw new Error("useErrors must be used within an ErrorProvider");
    }
    return context;
}

/**
 * Optional hook that returns null if not within an ErrorProvider.
 */
export function useErrorsOptional() {
    return useContext(ErrorContext);
}
