"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Edit2, X, Loader2 } from "lucide-react";
import { useFocusTrap } from "@/hooks/useFocusTrap";

export interface RenameDialogProps {
    isOpen: boolean;
    title: string;
    currentName: string;
    onConfirm: (newName: string) => Promise<void>;
    onCancel: () => void;
}

export function RenameDialog({
    isOpen,
    title,
    currentName,
    onConfirm,
    onCancel,
}: RenameDialogProps) {
    const [newName, setNewName] = useState(currentName);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const dialogRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Focus trap with Escape handling
    const handleClose = useCallback(() => {
        if (!isSubmitting) {
            onCancel();
        }
    }, [isSubmitting, onCancel]);

    const dialogA11yProps = useFocusTrap({
        isOpen,
        onClose: handleClose,
        containerRef: dialogRef,
        closeOnClickOutside: !isSubmitting,
    });

    // Reset name and focus input when dialog opens
    useEffect(() => {
        if (isOpen) {
            setNewName(currentName);
            // Focus input after a short delay to allow animation
            setTimeout(() => {
                inputRef.current?.focus();
                inputRef.current?.select();
            }, 100);
        }
    }, [isOpen, currentName]);

    // Lock body scroll when open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [isOpen]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newName.trim() || isSubmitting) return;

        try {
            setIsSubmitting(true);
            await onConfirm(newName);
        } finally {
            setIsSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

            {/* Dialog */}
            <div
                ref={dialogRef}
                {...dialogA11yProps}
                aria-labelledby="rename-dialog-title"
                className="relative z-10 w-full max-w-md mx-4 bg-white dark:bg-gray-800 rounded-xl shadow-2xl animate-in fade-in zoom-in-95 duration-200"
            >
                {/* Close button */}
                <button
                    onClick={onCancel}
                    disabled={isSubmitting}
                    className="absolute top-4 right-4 p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                    aria-label="Close"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="p-6">
                    {/* Icon and Title */}
                    <div className="flex items-start gap-4 mb-6">
                        <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
                            <Edit2 className="w-6 h-6" />
                        </div>
                        <div className="flex-1 pt-1">
                            <h3
                                id="rename-dialog-title"
                                className="text-lg font-semibold text-gray-900 dark:text-gray-100"
                            >
                                {title}
                            </h3>
                            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                                Enter a new name for this item.
                            </p>
                        </div>
                    </div>

                    <form onSubmit={handleSubmit}>
                        <div className="space-y-4">
                            <div>
                                <label htmlFor="name" className="sr-only">
                                    Name
                                </label>
                                <input
                                    ref={inputRef}
                                    id="name"
                                    type="text"
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder="Enter name..."
                                    disabled={isSubmitting}
                                    autoComplete="off"
                                />
                            </div>

                            <div className="flex gap-3 justify-end">
                                <button
                                    type="button"
                                    onClick={onCancel}
                                    disabled={isSubmitting}
                                    className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors disabled:opacity-50"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isSubmitting || !newName.trim() || newName === currentName}
                                    className="px-4 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                >
                                    {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                                    Save Changes
                                </button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
