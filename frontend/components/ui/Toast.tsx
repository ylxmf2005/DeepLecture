"use client";

import { useEffect, useState } from "react";
import { X, AlertCircle, AlertTriangle, Info, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AppError } from "@/hooks/useErrorHandler";

interface ToastProps {
    error: AppError;
    onDismiss: (id: string) => void;
}

const iconMap = {
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
    success: CheckCircle,
};

const styleMap = {
    error: "bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200",
    warning: "bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-200",
    info: "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200",
    success: "bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200",
};

export function Toast({ error, onDismiss }: ToastProps) {
    const [isVisible, setIsVisible] = useState(false);
    const Icon = iconMap[error.type];

    useEffect(() => {
        requestAnimationFrame(() => {
            setIsVisible(true);
        });
    }, []);

    const handleDismiss = () => {
        setIsVisible(false);
        setTimeout(() => onDismiss(error.id), 150);
    };

    return (
        <div
            className={cn(
                "flex items-start gap-3 p-4 rounded-lg border shadow-lg transition-all duration-150",
                styleMap[error.type],
                isVisible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-4"
            )}
        >
            <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{error.message}</p>
                {error.details && (
                    <p className="mt-1 text-xs opacity-75 line-clamp-2">{error.details}</p>
                )}
            </div>
            <button
                onClick={handleDismiss}
                className="flex-shrink-0 p-1 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                aria-label="Dismiss"
            >
                <X className="w-4 h-4" />
            </button>
        </div>
    );
}

interface ToastContainerProps {
    errors: AppError[];
    onDismiss: (id: string) => void;
}

export function ToastContainer({ errors, onDismiss }: ToastContainerProps) {
    if (errors.length === 0) return null;

    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full">
            {errors.map((error) => (
                <Toast key={error.id} error={error} onDismiss={onDismiss} />
            ))}
        </div>
    );
}
