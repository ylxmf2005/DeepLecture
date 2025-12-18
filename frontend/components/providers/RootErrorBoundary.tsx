"use client";

import { ReactNode } from "react";
import { ErrorBoundary } from "@/shared/infrastructure/ErrorBoundary";

interface RootErrorBoundaryProps {
    children: ReactNode;
}

/**
 * Global error boundary wrapper for the application root.
 * Catches unhandled errors and provides a recovery UI.
 */
export function RootErrorBoundary({ children }: RootErrorBoundaryProps) {
    return (
        <ErrorBoundary
            component="App"
            fallback={(error, reset) => (
                <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
                    <div className="max-w-md w-full p-8 bg-white dark:bg-gray-800 rounded-lg shadow-lg text-center">
                        <div className="text-red-500 mb-6">
                            <svg
                                className="w-16 h-16 mx-auto"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                                />
                            </svg>
                        </div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                            Something went wrong
                        </h1>
                        <p className="text-gray-600 dark:text-gray-400 mb-6 break-words text-left text-sm font-mono bg-gray-100 dark:bg-gray-900 p-3 rounded max-h-48 overflow-y-auto">
                            {error.message || "An unexpected error occurred"}
                        </p>
                        <div className="space-y-3">
                            <button
                                onClick={reset}
                                className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                            >
                                Try Again
                            </button>
                            <button
                                onClick={() => window.location.reload()}
                                className="w-full px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                            >
                                Reload Page
                            </button>
                        </div>
                    </div>
                </div>
            )}
        >
            {children}
        </ErrorBoundary>
    );
}
