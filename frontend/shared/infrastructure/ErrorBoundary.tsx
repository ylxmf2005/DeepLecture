"use client";

import { Component, ErrorInfo, ReactNode } from "react";
import { logger } from "./logger";
import { toError } from "@/lib/utils/errorUtils";

interface ErrorBoundaryProps {
    children: ReactNode;
    fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
    component?: string;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

/**
 * Error Boundary for graceful error handling in React components
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary component="VideoPlayer" fallback={<ErrorFallback />}>
 *   <VideoPlayer />
 * </ErrorBoundary>
 * ```
 *
 * Or with render prop for reset functionality:
 * ```tsx
 * <ErrorBoundary
 *   component="VideoPlayer"
 *   fallback={(error, reset) => (
 *     <div>
 *       <p>Error: {error.message}</p>
 *       <button onClick={reset}>Retry</button>
 *     </div>
 *   )}
 * >
 *   <VideoPlayer />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<
    ErrorBoundaryProps,
    ErrorBoundaryState
> {
    private log = logger.scope(this.props.component || "ErrorBoundary");

    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
        this.log.error("Component error caught", error, {
            componentStack: errorInfo.componentStack || "unknown",
        });

        this.props.onError?.(error, errorInfo);
    }

    private handleReset = (): void => {
        this.log.info("Error boundary reset requested");
        this.setState({ hasError: false, error: null });
    };

    render(): ReactNode {
        if (this.state.hasError && this.state.error) {
            const { fallback } = this.props;

            if (typeof fallback === "function") {
                return fallback(this.state.error, this.handleReset);
            }

            if (fallback) {
                return fallback;
            }

            // Default fallback UI
            return (
                <div className="flex flex-col items-center justify-center p-8 text-center">
                    <div className="text-red-500 mb-4">
                        <svg
                            className="w-12 h-12 mx-auto"
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
                    <h3 className="text-lg font-semibold mb-2">
                        Something went wrong
                    </h3>
                    <p className="text-sm text-muted-foreground mb-4 break-words text-left font-mono bg-muted p-2 rounded max-h-32 overflow-y-auto">
                        {this.state.error.message}
                    </p>
                    <button
                        onClick={this.handleReset}
                        className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
                    >
                        Try Again
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

/**
 * Hook version for functional components that need to report errors
 */
export function useErrorHandler(component?: string) {
    const log = logger.scope(component || "useErrorHandler");

    return {
        reportError: (error: Error, context?: Record<string, unknown>) => {
            log.error("Error reported", error, context);
        },
        wrapAsync: async <T,>(
            fn: () => Promise<T>,
            fallback?: T
        ): Promise<T | undefined> => {
            try {
                return await fn();
            } catch (error) {
                log.error(
                    "Async operation failed",
                    toError(error)
                );
                return fallback;
            }
        },
    };
}
