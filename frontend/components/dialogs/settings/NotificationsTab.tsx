"use client";

import { Bell } from "lucide-react";
import { useTaskNotification } from "@/hooks/useTaskNotification";
import { SettingsSection, SettingsCard, SettingsRow } from "./SettingsSection";
import { ToggleSwitch } from "./ToggleSwitch";
import { ScopeAwareField } from "./ScopeAwareField";
import type { SettingsTabProps } from "./types";

export function NotificationsTab({ scope, settings }: SettingsTabProps) {
    const isVideoScope = scope === "video";
    const { values, isOverridden, clearField } = settings;
    const { notifications } = values;

    const { browserPermissionStatus, requestNotificationPermission } = useTaskNotification();

    return (
        <SettingsSection icon={Bell} title="Task Notifications" accentColor="orange">
            <SettingsCard>
                <ScopeAwareField path="notifications.toastNotificationsEnabled" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                    <SettingsRow
                        label="Toast Notifications"
                        description="Show in-app notifications when tasks complete"
                    >
                        <ToggleSwitch
                            enabled={notifications.toastNotificationsEnabled}
                            onChange={() => settings.setToastNotificationsEnabled(!notifications.toastNotificationsEnabled)}
                            accentColor="orange"
                        />
                    </SettingsRow>
                </ScopeAwareField>

                <ScopeAwareField path="notifications.titleFlashEnabled" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                    <SettingsRow
                        label="Title Flash"
                        description="Flash page title when tasks complete in background"
                        withBorder
                    >
                        <ToggleSwitch
                            enabled={notifications.titleFlashEnabled}
                            onChange={() => settings.setTitleFlashEnabled(!notifications.titleFlashEnabled)}
                            accentColor="orange"
                        />
                    </SettingsRow>
                </ScopeAwareField>

                <ScopeAwareField path="notifications.browserNotificationsEnabled" isOverridden={isOverridden} onReset={clearField} isVideoScope={isVideoScope}>
                    <SettingsRow
                        label="Browser Notifications"
                        description={
                            browserPermissionStatus === "unsupported"
                                ? "Not supported in this browser"
                                : browserPermissionStatus === "denied"
                                  ? "Permission denied - enable in browser settings"
                                  : "System notifications when tab is in background"
                        }
                        withBorder
                    >
                        {browserPermissionStatus === "granted" ? (
                            <ToggleSwitch
                                enabled={notifications.browserNotificationsEnabled}
                                onChange={() => settings.setBrowserNotificationsEnabled(!notifications.browserNotificationsEnabled)}
                                accentColor="orange"
                            />
                        ) : browserPermissionStatus === "default" ? (
                            <button
                                type="button"
                                onClick={async () => {
                                    const granted = await requestNotificationPermission();
                                    if (granted) {
                                        settings.setBrowserNotificationsEnabled(true);
                                    }
                                }}
                                className="px-3 py-1.5 text-xs font-medium text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 rounded-lg hover:bg-orange-100 dark:hover:bg-orange-900/30 transition-colors"
                            >
                                Enable
                            </button>
                        ) : (
                            <span className="text-xs text-gray-400 dark:text-gray-500">Unavailable</span>
                        )}
                    </SettingsRow>
                </ScopeAwareField>
            </SettingsCard>

            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                Get notified when background tasks like subtitle generation, translation, or video processing complete.
            </p>
        </SettingsSection>
    );
}
