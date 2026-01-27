"use client";

import type { ReactNode } from "react";
import { Component } from "react";

interface ErrorBoundaryProps {
    component: string;
    children: ReactNode;
    fallback: ReactNode | ((error: Error, reset: () => void) => ReactNode);
}

interface ErrorBoundaryState {
    error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { error: null };

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { error };
    }

    private reset = () => {
        this.setState({ error: null });
    };

    render() {
        const { error } = this.state;
        if (!error) return this.props.children;

        const { fallback } = this.props;
        if (typeof fallback === "function") {
            return fallback(error, this.reset);
        }
        return fallback;
    }
}

