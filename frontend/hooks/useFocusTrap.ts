/**
 * Focus trap hook for accessible modal dialogs.
 *
 * Provides:
 * - Focus trapping within dialog
 * - Escape key to close
 * - Focus restoration on close
 * - ARIA attributes
 */

import { useEffect, useRef, useCallback, RefObject } from "react";

export interface UseFocusTrapOptions {
    isOpen: boolean;
    onClose: () => void;
    /** Ref to the dialog container element */
    containerRef: RefObject<HTMLElement | null>;
    /** Whether to close on Escape key (default: true) */
    closeOnEscape?: boolean;
    /** Whether to close on clicking outside (default: true) */
    closeOnClickOutside?: boolean;
}

const FOCUSABLE_SELECTOR =
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Get all focusable elements within a container.
 */
function getFocusableElements(container: HTMLElement): HTMLElement[] {
    return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
}

/**
 * Hook for implementing focus trap in modal dialogs.
 * Returns props to spread onto the dialog container.
 */
export function useFocusTrap({
    isOpen,
    onClose,
    containerRef,
    closeOnEscape = true,
    closeOnClickOutside = true,
}: UseFocusTrapOptions) {
    const previousActiveElementRef = useRef<Element | null>(null);

    // Store the previously focused element when opening
    useEffect(() => {
        if (isOpen) {
            previousActiveElementRef.current = document.activeElement;
        }
    }, [isOpen]);

    // Focus first element when dialog opens, restore focus when closing
    useEffect(() => {
        if (!isOpen || !containerRef.current) return;

        const container = containerRef.current;
        const focusableElements = getFocusableElements(container);

        // Focus the first focusable element
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        } else {
            // If no focusable elements, focus the container itself
            container.focus();
        }

        return () => {
            // Restore focus when closing
            const previousElement = previousActiveElementRef.current;
            if (previousElement instanceof HTMLElement) {
                previousElement.focus();
            }
        };
    }, [isOpen, containerRef]);

    // Handle keyboard events
    const handleKeyDown = useCallback(
        (event: KeyboardEvent) => {
            if (!isOpen || !containerRef.current) return;

            // Handle Escape key
            if (event.key === "Escape" && closeOnEscape) {
                event.preventDefault();
                onClose();
                return;
            }

            // Handle Tab key for focus trapping
            if (event.key === "Tab") {
                const container = containerRef.current;
                const focusableElements = getFocusableElements(container);

                if (focusableElements.length === 0) {
                    event.preventDefault();
                    return;
                }

                const firstElement = focusableElements[0];
                const lastElement = focusableElements[focusableElements.length - 1];

                // Shift+Tab on first element -> go to last
                if (event.shiftKey && document.activeElement === firstElement) {
                    event.preventDefault();
                    lastElement.focus();
                }
                // Tab on last element -> go to first
                else if (!event.shiftKey && document.activeElement === lastElement) {
                    event.preventDefault();
                    firstElement.focus();
                }
            }
        },
        [isOpen, containerRef, onClose, closeOnEscape]
    );

    // Handle click outside
    const handleClickOutside = useCallback(
        (event: MouseEvent) => {
            if (!isOpen || !closeOnClickOutside || !containerRef.current) return;

            if (!containerRef.current.contains(event.target as Node)) {
                onClose();
            }
        },
        [isOpen, closeOnClickOutside, containerRef, onClose]
    );

    // Add event listeners
    useEffect(() => {
        if (!isOpen) return;

        document.addEventListener("keydown", handleKeyDown);
        document.addEventListener("mousedown", handleClickOutside);

        return () => {
            document.removeEventListener("keydown", handleKeyDown);
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [isOpen, handleKeyDown, handleClickOutside]);

    // Return ARIA props for the dialog container
    return {
        role: "dialog" as const,
        "aria-modal": true,
        tabIndex: -1, // Allow focus on container if no focusable children
    };
}

/**
 * Simple wrapper component props for accessible dialogs.
 */
export interface DialogA11yProps {
    role: "dialog";
    "aria-modal": true;
    tabIndex: number;
}
