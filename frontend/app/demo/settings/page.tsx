"use client";

import { useState } from "react";
import {
  Globe,
  Video,
  Languages,
  Bot,
  Subtitles,
  SlidersHorizontal,
  Bell,
  Sparkles,
  FileText,
  RotateCcw,
  Lock,
  ChevronDown,
  X,
  BookOpen,
  MessageSquare,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────

type Scope = "global" | "video";

type TabId =
  | "language"
  | "models"
  | "prompts"
  | "player"
  | "functions"
  | "notifications";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
  /** Fields in this tab can be overridden per-video */
  hasVideoScope: boolean;
}

const TABS: Tab[] = [
  {
    id: "language",
    label: "Language",
    icon: <Languages className="w-4 h-4" />,
    hasVideoScope: true,
  },
  {
    id: "models",
    label: "AI Models",
    icon: <Bot className="w-4 h-4" />,
    hasVideoScope: true,
  },
  {
    id: "prompts",
    label: "Prompts",
    icon: <MessageSquare className="w-4 h-4" />,
    hasVideoScope: true,
  },
  {
    id: "functions",
    label: "Functions",
    icon: <SlidersHorizontal className="w-4 h-4" />,
    hasVideoScope: true,
  },
  {
    id: "player",
    label: "Player",
    icon: <Subtitles className="w-4 h-4" />,
    hasVideoScope: false,
  },
  {
    id: "notifications",
    label: "Notifications",
    icon: <Bell className="w-4 h-4" />,
    hasVideoScope: false,
  },
];

// ─── Mock override state ──────────────────────────────

const INITIAL_OVERRIDES: Record<string, string | null> = {
  sourceLanguage: null,
  targetLanguage: "Chinese (Simplified)",
  llmModel: "claude-sonnet-4-20250514",
  ttsModel: null,
  learnerProfile: null,
  noteContextMode: null,
  promptAsk: null,
  promptNote: "You are a concise note taker focusing on key concepts...",
};

// ─── Reusable pieces ─────────────────────────────────

function ScopeSwitcher({
  scope,
  onScopeChange,
}: {
  scope: Scope;
  onScopeChange: (s: Scope) => void;
}) {
  return (
    <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1 gap-1">
      <button
        onClick={() => onScopeChange("global")}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
          scope === "global"
            ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
            : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
        }`}
      >
        <Globe className="w-3.5 h-3.5" />
        Global
      </button>
      <button
        onClick={() => onScopeChange("video")}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
          scope === "video"
            ? "bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm"
            : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
        }`}
      >
        <Video className="w-3.5 h-3.5" />
        This Video
      </button>
    </div>
  );
}

function OverrideBadge() {
  return (
    <span className="text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded">
      Override
    </span>
  );
}

function GlobalOnlyBanner() {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/40 text-amber-700 dark:text-amber-400 text-xs">
      <Lock className="w-3.5 h-3.5 shrink-0" />
      <span>
        These settings apply globally and cannot be overridden per video.
      </span>
    </div>
  );
}

function ResetButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1 transition-colors"
    >
      <RotateCcw className="w-3 h-3" />
      Reset
    </button>
  );
}

// ─── Field wrapper for scope-aware fields ─────────────

function FieldRow({
  label,
  description,
  scope,
  overrideValue,
  onReset,
  globalOnly,
  children,
}: {
  label: string;
  description?: string;
  scope: Scope;
  overrideValue?: string | null;
  onReset?: () => void;
  globalOnly?: boolean;
  children: React.ReactNode;
}) {
  const isOverridden = scope === "video" && overrideValue != null;
  const isDisabled = scope === "video" && globalOnly;

  return (
    <div
      className={`space-y-1.5 ${isDisabled ? "opacity-40 pointer-events-none select-none" : ""}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            {label}
          </label>
          {isOverridden && <OverrideBadge />}
        </div>
        {isOverridden && onReset && <ResetButton onClick={onReset} />}
      </div>
      {children}
      {description && (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {description}
        </p>
      )}
    </div>
  );
}

// ─── Mock select component ────────────────────────────

function MockSelect({
  value,
  placeholder,
  disabled,
  accent = "indigo",
}: {
  value: string;
  placeholder?: string;
  disabled?: boolean;
  accent?: "indigo" | "emerald" | "rose" | "cyan";
}) {
  const accentRing = {
    indigo: "focus:ring-indigo-500/30 focus:border-indigo-500",
    emerald: "focus:ring-emerald-500/30 focus:border-emerald-500",
    rose: "focus:ring-rose-500/30 focus:border-rose-500",
    cyan: "focus:ring-cyan-500/30 focus:border-cyan-500",
  };

  const displayValue = value || placeholder;
  const isPlaceholder = !value;

  return (
    <div
      className={`
        flex items-center justify-between px-3 py-2 rounded-lg border-2
        border-gray-200 dark:border-gray-700
        bg-white dark:bg-gray-800
        ${disabled ? "cursor-not-allowed" : "cursor-pointer hover:border-gray-300 dark:hover:border-gray-600"}
        ${accentRing[accent]}
        transition-colors
      `}
    >
      <span
        className={
          isPlaceholder
            ? "text-sm text-gray-400 dark:text-gray-500"
            : "text-sm text-gray-900 dark:text-gray-100"
        }
      >
        {displayValue}
      </span>
      <ChevronDown className="w-4 h-4 text-gray-400" />
    </div>
  );
}

// ─── Section header ───────────────────────────────────

function SectionHeader({
  icon,
  title,
  accent = "blue",
}: {
  icon: React.ReactNode;
  title: string;
  accent?: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "text-blue-600 dark:text-blue-400",
    indigo: "text-indigo-600 dark:text-indigo-400",
    emerald: "text-emerald-600 dark:text-emerald-400",
    rose: "text-rose-600 dark:text-rose-400",
    amber: "text-amber-600 dark:text-amber-400",
    violet: "text-violet-600 dark:text-violet-400",
  };

  return (
    <div className={`flex items-center gap-2 ${colorMap[accent] ?? colorMap.blue}`}>
      {icon}
      <h3 className="font-semibold text-sm">{title}</h3>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-700 p-5 shadow-sm space-y-5">
      {children}
    </div>
  );
}

// ─── Tab content ──────────────────────────────────────

function LanguageTab({
  scope,
  overrides,
  onReset,
}: {
  scope: Scope;
  overrides: Record<string, string | null>;
  onReset: (field: string) => void;
}) {
  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Languages className="w-5 h-5" />}
        title="Language"
        accent="blue"
      />
      <Card>
        <FieldRow
          label="Source Language"
          description="Language spoken in the video"
          scope={scope}
          overrideValue={overrides.sourceLanguage}
          onReset={() => onReset("sourceLanguage")}
        >
          <MockSelect
            value={
              scope === "video" && overrides.sourceLanguage != null
                ? overrides.sourceLanguage
                : "English"
            }
            placeholder={scope === "video" ? "Use global default" : undefined}
          />
        </FieldRow>

        <div className="border-t border-gray-100 dark:border-gray-700" />

        <FieldRow
          label="Target Language"
          description="Used for translations, explanations, notes"
          scope={scope}
          overrideValue={overrides.targetLanguage}
          onReset={() => onReset("targetLanguage")}
        >
          <MockSelect
            value={
              scope === "video" && overrides.targetLanguage != null
                ? overrides.targetLanguage
                : scope === "video"
                  ? ""
                  : "Japanese"
            }
            placeholder={scope === "video" ? "Use global default" : undefined}
          />
        </FieldRow>
      </Card>

      <SectionHeader
        icon={<BookOpen className="w-5 h-5" />}
        title="Learner Profile"
        accent="violet"
      />
      <Card>
        <FieldRow
          label="Profile"
          description="Describe your background so AI can tailor explanations"
          scope={scope}
          overrideValue={overrides.learnerProfile}
          onReset={() => onReset("learnerProfile")}
        >
          <textarea
            className="w-full px-3 py-2 rounded-lg border-2 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 transition-colors resize-none"
            rows={3}
            placeholder={
              scope === "video"
                ? "Use global default"
                : "e.g. CS graduate student interested in distributed systems"
            }
            defaultValue={
              scope === "global"
                ? "CS graduate student interested in distributed systems"
                : ""
            }
          />
        </FieldRow>
      </Card>
    </div>
  );
}

function ModelsTab({
  scope,
  overrides,
  onReset,
}: {
  scope: Scope;
  overrides: Record<string, string | null>;
  onReset: (field: string) => void;
}) {
  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Bot className="w-5 h-5" />}
        title="AI Models"
        accent="indigo"
      />
      <Card>
        <FieldRow
          label="LLM Model"
          description="Used for Q&A, explanations, notes, timeline"
          scope={scope}
          overrideValue={overrides.llmModel}
          onReset={() => onReset("llmModel")}
        >
          <MockSelect
            value={
              scope === "video" && overrides.llmModel != null
                ? overrides.llmModel
                : scope === "video"
                  ? ""
                  : "gpt-4o"
            }
            placeholder={scope === "video" ? "Use global default" : undefined}
            accent="indigo"
          />
        </FieldRow>

        <div className="border-t border-gray-100 dark:border-gray-700" />

        <FieldRow
          label="TTS Model"
          description="Used for voiceover generation"
          scope={scope}
          overrideValue={overrides.ttsModel}
          onReset={() => onReset("ttsModel")}
        >
          <MockSelect
            value={
              scope === "video" && overrides.ttsModel != null
                ? overrides.ttsModel
                : scope === "video"
                  ? ""
                  : "openai/alloy"
            }
            placeholder={scope === "video" ? "Use global default" : undefined}
            accent="rose"
          />
        </FieldRow>
      </Card>
    </div>
  );
}

function PromptsTab({
  scope,
  overrides,
  onReset,
}: {
  scope: Scope;
  overrides: Record<string, string | null>;
  onReset: (field: string) => void;
}) {
  const prompts = [
    { key: "promptAsk", label: "Ask / Q&A", accent: "indigo" as const },
    { key: "promptNote", label: "Note Generation", accent: "emerald" as const },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<MessageSquare className="w-5 h-5" />}
        title="Prompt Templates"
        accent="emerald"
      />
      {prompts.map((p) => (
        <Card key={p.key}>
          <FieldRow
            label={p.label}
            description="Customize the system prompt for this function"
            scope={scope}
            overrideValue={overrides[p.key]}
            onReset={() => onReset(p.key)}
          >
            <textarea
              className={`w-full px-3 py-2 rounded-lg border-2 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-${p.accent}-500/20 focus:border-${p.accent}-500 transition-colors resize-none font-mono`}
              rows={4}
              placeholder={
                scope === "video" ? "Use global default" : "Enter prompt..."
              }
              defaultValue={
                scope === "video" && overrides[p.key] != null
                  ? overrides[p.key]!
                  : scope === "global"
                    ? "You are a helpful teaching assistant..."
                    : ""
              }
            />
          </FieldRow>
        </Card>
      ))}
    </div>
  );
}

function FunctionsTab({
  scope,
  overrides,
  onReset,
}: {
  scope: Scope;
  overrides: Record<string, string | null>;
  onReset: (field: string) => void;
}) {
  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<SlidersHorizontal className="w-5 h-5" />}
        title="Functions"
        accent="amber"
      />
      <Card>
        <FieldRow
          label="Note Context Mode"
          description="What context to include when generating notes"
          scope={scope}
          overrideValue={overrides.noteContextMode}
          onReset={() => onReset("noteContextMode")}
        >
          <MockSelect
            value={
              scope === "video" && overrides.noteContextMode != null
                ? overrides.noteContextMode
                : scope === "video"
                  ? ""
                  : "Subtitle + Slide"
            }
            placeholder={scope === "video" ? "Use global default" : undefined}
            accent="emerald"
          />
        </FieldRow>
      </Card>

      {/* Global-only fields in this tab */}
      <SectionHeader
        icon={<Sparkles className="w-5 h-5" />}
        title="Dictionary"
        accent="amber"
      />
      {scope === "video" && <GlobalOnlyBanner />}
      <Card>
        <FieldRow
          label="Dictionary Lookup"
          description="Enable dictionary lookup for subtitles"
          scope={scope}
          globalOnly
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-6 bg-blue-500 rounded-full relative">
              <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow" />
            </div>
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Enabled
            </span>
          </div>
        </FieldRow>

        <div className="border-t border-gray-100 dark:border-gray-700" />

        <FieldRow
          label="Interaction Mode"
          description="How to trigger dictionary lookup"
          scope={scope}
          globalOnly
        >
          <MockSelect value="Hover" accent="emerald" />
        </FieldRow>
      </Card>
    </div>
  );
}

function PlayerTab({ scope }: { scope: Scope }) {
  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Subtitles className="w-5 h-5" />}
        title="Player & Subtitles"
        accent="emerald"
      />
      {scope === "video" && <GlobalOnlyBanner />}
      <Card>
        <FieldRow
          label="Subtitle Font Size"
          description="Display size of subtitles on video"
          scope={scope}
          globalOnly
        >
          <MockSelect value="Medium (18px)" accent="emerald" />
        </FieldRow>

        <div className="border-t border-gray-100 dark:border-gray-700" />

        <FieldRow
          label="Auto Pause on Leave"
          description="Automatically pause video when you switch tabs"
          scope={scope}
          globalOnly
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-6 bg-blue-500 rounded-full relative">
              <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow" />
            </div>
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Enabled
            </span>
          </div>
        </FieldRow>

        <div className="border-t border-gray-100 dark:border-gray-700" />

        <FieldRow
          label="Auto Switch Voiceover on Leave"
          description="Switch to voiceover audio when you leave the tab"
          scope={scope}
          globalOnly
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-6 bg-gray-300 dark:bg-gray-600 rounded-full relative">
              <div className="absolute left-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow" />
            </div>
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Disabled
            </span>
          </div>
        </FieldRow>
      </Card>
    </div>
  );
}

function NotificationsTab({ scope }: { scope: Scope }) {
  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Bell className="w-5 h-5" />}
        title="Notifications"
        accent="rose"
      />
      {scope === "video" && <GlobalOnlyBanner />}
      <Card>
        <FieldRow
          label="Browser Notifications"
          description="Show system notifications when tasks complete"
          scope={scope}
          globalOnly
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-6 bg-blue-500 rounded-full relative">
              <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow" />
            </div>
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Enabled
            </span>
          </div>
        </FieldRow>

        <div className="border-t border-gray-100 dark:border-gray-700" />

        <FieldRow
          label="Toast Notifications"
          description="Show in-app toast when tasks complete"
          scope={scope}
          globalOnly
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-6 bg-blue-500 rounded-full relative">
              <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow" />
            </div>
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Enabled
            </span>
          </div>
        </FieldRow>
      </Card>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────

export default function SettingsDemoPage() {
  const [scope, setScope] = useState<Scope>("global");
  const [activeTab, setActiveTab] = useState<TabId>("language");
  const [overrides, setOverrides] = useState(INITIAL_OVERRIDES);

  const handleReset = (field: string) => {
    setOverrides((prev) => ({ ...prev, [field]: null }));
  };

  const handleResetAll = () => {
    setOverrides(
      Object.fromEntries(Object.keys(overrides).map((k) => [k, null]))
    );
  };

  const overrideCount = Object.values(overrides).filter(
    (v) => v != null
  ).length;

  const renderTab = () => {
    switch (activeTab) {
      case "language":
        return (
          <LanguageTab
            scope={scope}
            overrides={overrides}
            onReset={handleReset}
          />
        );
      case "models":
        return (
          <ModelsTab
            scope={scope}
            overrides={overrides}
            onReset={handleReset}
          />
        );
      case "prompts":
        return (
          <PromptsTab
            scope={scope}
            overrides={overrides}
            onReset={handleReset}
          />
        );
      case "functions":
        return (
          <FunctionsTab
            scope={scope}
            overrides={overrides}
            onReset={handleReset}
          />
        );
      case "player":
        return <PlayerTab scope={scope} />;
      case "notifications":
        return <NotificationsTab scope={scope} />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950 flex items-center justify-center p-4">
      {/* Simulated dialog */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col animate-in zoom-in-95 duration-200">
        {/* ── Header ──────────────────────────── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Settings
              </h2>
              {scope === "video" && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  System Security L3.mp4
                </p>
              )}
            </div>
            <ScopeSwitcher scope={scope} onScopeChange={setScope} />
          </div>

          <div className="flex items-center gap-3">
            {scope === "video" && overrideCount > 0 && (
              <button
                onClick={handleResetAll}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg transition-colors"
              >
                <RotateCcw className="w-3 h-3" />
                Reset All ({overrideCount})
              </button>
            )}
            <button className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* ── Body ────────────────────────────── */}
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-48 bg-gray-50 dark:bg-gray-900/50 border-r border-gray-200 dark:border-gray-800 py-3 px-2 space-y-0.5 overflow-y-auto">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              const isGlobalOnly = scope === "video" && !tab.hasVideoScope;

              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all
                    ${
                      isActive
                        ? "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
                        : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200"
                    }
                    ${isGlobalOnly ? "opacity-50" : ""}
                  `}
                >
                  {tab.icon}
                  <span className="flex-1 text-left">{tab.label}</span>
                  {isGlobalOnly && (
                    <Lock className="w-3 h-3 text-gray-400 dark:text-gray-500" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 bg-gray-50/50 dark:bg-gray-900/50">
            <div className="max-w-xl mx-auto">{renderTab()}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
