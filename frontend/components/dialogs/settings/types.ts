import type { LucideIcon } from "lucide-react";
import type { ContentItem, Live2DModel, ModelOption } from "@/lib/api";
import type { ScopedSettings, SettingsScope } from "./useSettingsScope";

export type TabId = "general" | "notifications" | "player" | "functions" | "model" | "live2d" | "prompt";

export interface TabDefinition {
    id: TabId;
    label: string;
    icon: LucideIcon;
}

export interface SettingsSectionProps {
    icon: LucideIcon;
    title: string;
    accentColor: string;
    children: React.ReactNode;
    /** Optional hint displayed below the section title (e.g. "default for all videos") */
    hint?: string;
}

export interface ToggleSwitchProps {
    enabled: boolean;
    onChange: () => void;
    disabled?: boolean;
    accentColor?: string;
}

export interface SettingsTabProps {
    video?: ContentItem;
    scope: SettingsScope;
    settings: ScopedSettings;
}

export interface ModelTabData {
    llmModels: ModelOption[];
    defaultLlmModel: string;
    ttsModels: ModelOption[];
    defaultTtsModel: string;
    loading: boolean;
}

export interface Live2DTabData {
    live2dModels: Live2DModel[];
    modelsLoading: boolean;
}
