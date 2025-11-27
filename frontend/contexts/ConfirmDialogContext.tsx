"use client";

import { createContext, useContext, useState, useCallback, ReactNode, useRef } from "react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

export interface ConfirmOptions {
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: "danger" | "warning" | "default";
}

interface ConfirmDialogContextValue {
    confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const ConfirmDialogContext = createContext<ConfirmDialogContextValue | null>(null);

interface ConfirmDialogProviderProps {
    children: ReactNode;
}

export function ConfirmDialogProvider({ children }: ConfirmDialogProviderProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [options, setOptions] = useState<ConfirmOptions | null>(null);
    const resolverRef = useRef<((value: boolean) => void) | null>(null);

    const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
        return new Promise((resolve) => {
            setOptions(opts);
            setIsOpen(true);
            resolverRef.current = resolve;
        });
    }, []);

    const handleConfirm = useCallback(() => {
        setIsOpen(false);
        resolverRef.current?.(true);
        resolverRef.current = null;
    }, []);

    const handleCancel = useCallback(() => {
        setIsOpen(false);
        resolverRef.current?.(false);
        resolverRef.current = null;
    }, []);

    return (
        <ConfirmDialogContext.Provider value={{ confirm }}>
            {children}
            {options && (
                <ConfirmDialog
                    isOpen={isOpen}
                    title={options.title}
                    message={options.message}
                    confirmLabel={options.confirmLabel}
                    cancelLabel={options.cancelLabel}
                    variant={options.variant}
                    onConfirm={handleConfirm}
                    onCancel={handleCancel}
                />
            )}
        </ConfirmDialogContext.Provider>
    );
}

export function useConfirmDialog() {
    const context = useContext(ConfirmDialogContext);
    if (!context) {
        throw new Error("useConfirmDialog must be used within a ConfirmDialogProvider");
    }
    return context;
}
