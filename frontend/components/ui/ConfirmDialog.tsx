"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ConfirmDialogProps {
    isOpen: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: "danger" | "warning" | "default";
    onConfirm: () => void;
    onCancel: () => void;
}

export function ConfirmDialog({
    isOpen,
    title,
    message,
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    variant = "danger",
    onConfirm,
    onCancel,
}: ConfirmDialogProps) {
    const dialogRef = useRef<HTMLDivElement>(null);
    const confirmButtonRef = useRef<HTMLButtonElement>(null);

    // Focus trap and escape key handling
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                onCancel();
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        confirmButtonRef.current?.focus();

        // Prevent body scroll when dialog is open
        document.body.style.overflow = "hidden";

        return () => {
            document.removeEventListener("keydown", handleKeyDown);
            document.body.style.overflow = "";
        };
    }, [isOpen, onCancel]);

    if (!isOpen) return null;

    const variantStyles = {
        danger: {
            icon: "bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400",
            button: "bg-red-600 hover:bg-red-700 focus:ring-red-500",
        },
        warning: {
            icon: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400",
            button: "bg-yellow-600 hover:bg-yellow-700 focus:ring-yellow-500",
        },
        default: {
            icon: "bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400",
            button: "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500",
        },
    };

    const styles = variantStyles[variant];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/50 backdrop-blur-sm"
                onClick={onCancel}
            />

            {/* Dialog */}
            <div
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="confirm-dialog-title"
                aria-describedby="confirm-dialog-message"
                className="relative z-10 w-full max-w-md mx-4 bg-white dark:bg-gray-800 rounded-xl shadow-2xl animate-in fade-in zoom-in-95 duration-200"
            >
                {/* Close button */}
                <button
                    onClick={onCancel}
                    className="absolute top-4 right-4 p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    aria-label="Close"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="p-6">
                    {/* Icon and Title */}
                    <div className="flex items-start gap-4">
                        <div className={cn("p-3 rounded-full", styles.icon)}>
                            <AlertTriangle className="w-6 h-6" />
                        </div>
                        <div className="flex-1 pt-1">
                            <h3
                                id="confirm-dialog-title"
                                className="text-lg font-semibold text-gray-900 dark:text-gray-100"
                            >
                                {title}
                            </h3>
                            <p
                                id="confirm-dialog-message"
                                className="mt-2 text-sm text-gray-600 dark:text-gray-400"
                            >
                                {message}
                            </p>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="mt-6 flex gap-3 justify-end">
                        <button
                            onClick={onCancel}
                            className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors"
                        >
                            {cancelLabel}
                        </button>
                        <button
                            ref={confirmButtonRef}
                            onClick={onConfirm}
                            className={cn(
                                "px-4 py-2 text-sm font-medium rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors",
                                styles.button
                            )}
                        >
                            {confirmLabel}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
