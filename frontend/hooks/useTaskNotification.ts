"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useNotificationSettings } from "@/stores/useGlobalSettingsStore";

type TaskType =
    | "subtitle_generation"
    | "subtitle_enhancement"
    | "subtitle_translation"
    | "timeline_generation"
    | "video_generation"
    | "video_merge"
    | "video_import_url"
    | "pdf_merge"
    | "slide_explanation";

const readNotificationPermission = () =>
    typeof window !== "undefined" && "Notification" in window ? Notification.permission : "unsupported";

const TASK_LABELS: Record<TaskType, { success: string; error: string }> = {
    subtitle_generation: {
        success: "Subtitles generated successfully",
        error: "Subtitle generation failed",
    },
    subtitle_enhancement: {
        success: "Subtitles enhanced successfully",
        error: "Subtitle enhancement failed",
    },
    subtitle_translation: {
        success: "Translation completed",
        error: "Translation failed",
    },
    timeline_generation: {
        success: "Timeline generated successfully",
        error: "Timeline generation failed",
    },
    video_generation: {
        success: "Video generated successfully",
        error: "Video generation failed",
    },
    video_merge: {
        success: "Videos merged successfully",
        error: "Video merge failed",
    },
    video_import_url: {
        success: "Video imported successfully",
        error: "Video import failed",
    },
    pdf_merge: {
        success: "PDFs merged successfully",
        error: "PDF merge failed",
    },
    slide_explanation: {
        success: "Slide explanation ready",
        error: "Slide explanation failed",
    },
};

interface UseTaskNotificationReturn {
    notifyTaskComplete: (taskType: string, status: "ready" | "error", errorMessage?: string) => void;
    requestNotificationPermission: () => Promise<boolean>;
    browserPermissionStatus: NotificationPermission | "unsupported";
}

export function useTaskNotification(): UseTaskNotificationReturn {
    const settings = useNotificationSettings();
    const originalTitleRef = useRef<string>("");
    const titleIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const [browserPermissionStatus, setBrowserPermissionStatus] = useState<NotificationPermission | "unsupported">(
        readNotificationPermission
    );

    // Store original title on mount
    useEffect(() => {
        originalTitleRef.current = document.title;
        return () => {
            // Cleanup: restore title and clear interval
            if (titleIntervalRef.current) {
                clearInterval(titleIntervalRef.current);
            }
            document.title = originalTitleRef.current;
        };
    }, []);

    // Stop title flashing when tab becomes visible
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState === "visible" && titleIntervalRef.current) {
                clearInterval(titleIntervalRef.current);
                titleIntervalRef.current = null;
                document.title = originalTitleRef.current;
            }
        };

        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
    }, []);

    // Keep local permission state in sync so consumers re-render immediately after user decision
    useEffect(() => {
        setBrowserPermissionStatus(readNotificationPermission());
    }, []);

    const requestNotificationPermission = useCallback(async (): Promise<boolean> => {
        if (!("Notification" in window)) {
            setBrowserPermissionStatus("unsupported");
            return false;
        }

        if (Notification.permission === "granted") {
            setBrowserPermissionStatus("granted");
            return true;
        }

        if (Notification.permission === "denied") {
            setBrowserPermissionStatus("denied");
            return false;
        }

        const permission = await Notification.requestPermission();
        setBrowserPermissionStatus(permission);
        return permission === "granted";
    }, []);

    const flashTitle = useCallback((message: string) => {
        if (document.visibilityState === "visible") {
            return; // Don't flash if tab is visible
        }

        // Clear any existing interval
        if (titleIntervalRef.current) {
            clearInterval(titleIntervalRef.current);
        }

        let showMessage = true;
        titleIntervalRef.current = setInterval(() => {
            document.title = showMessage ? `✓ ${message}` : originalTitleRef.current;
            showMessage = !showMessage;
        }, 1000);

        // Auto-stop after 30 seconds
        setTimeout(() => {
            if (titleIntervalRef.current) {
                clearInterval(titleIntervalRef.current);
                titleIntervalRef.current = null;
                document.title = originalTitleRef.current;
            }
        }, 30000);
    }, []);

    const sendBrowserNotification = useCallback((title: string, body?: string) => {
        if (!("Notification" in window) || Notification.permission !== "granted") {
            return;
        }

        // Only send if tab is not visible
        if (document.visibilityState === "visible") {
            return;
        }

        new Notification(title, {
            body,
            icon: "/favicon.ico",
            tag: "task-complete", // Prevents duplicate notifications
        });
    }, []);

    const notifyTaskComplete = useCallback(
        (taskType: string, status: "ready" | "error", errorMessage?: string) => {
            const labels = TASK_LABELS[taskType as TaskType];
            if (!labels) {
                return; // Unknown task type, skip notification
            }

            const isSuccess = status === "ready";
            const message = isSuccess ? labels.success : labels.error;

            // 1. Toast notification (if enabled)
            if (settings.toastNotificationsEnabled) {
                if (isSuccess) {
                    toast.success(message);
                } else {
                    toast.error(message, {
                        description: errorMessage,
                    });
                }
            }

            // 2. Flash title (if enabled and tab is in background)
            if (settings.titleFlashEnabled && isSuccess) {
                flashTitle(message);
            }

            // 3. Browser notification (if enabled, permitted, and tab is hidden)
            if (settings.browserNotificationsEnabled) {
                if (isSuccess) {
                    sendBrowserNotification("Task Complete", message);
                } else {
                    sendBrowserNotification("Task Failed", message);
                }
            }
        },
        [settings, flashTitle, sendBrowserNotification]
    );

    return {
        notifyTaskComplete,
        requestNotificationPermission,
        browserPermissionStatus,
    };
}
