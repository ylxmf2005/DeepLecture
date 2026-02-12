/**
 * Unit tests for config resolution (resolveSettings + utilities).
 *
 * The resolveSettings function merges global settings with per-video overrides.
 */

import { describe, it, expect } from "vitest";
import type { GlobalSettings, PerVideoConfig } from "@/stores/types";
import { DEFAULT_GLOBAL_SETTINGS } from "@/stores/types";
import {
    resolveSettings,
    toTaskConfig,
    isFieldOverridden,
    countOverrides,
    setOverrideField,
    clearOverrideField,
} from "@/lib/configResolution";

describe("resolveSettings", () => {
    const global = DEFAULT_GLOBAL_SETTINGS;

    it("should return global unchanged when per-video is null", () => {
        const result = resolveSettings(global, null);
        expect(result).toBe(global); // same reference
    });

    it("should return global unchanged when per-video is empty", () => {
        const result = resolveSettings(global, {});
        expect(result).toBe(global); // same reference (fast path)
    });

    // ── Language ─────────────────────────────────────────────

    it("should override language fields", () => {
        const perVideo: PerVideoConfig = {
            language: { original: "ja" },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.language.original).toBe("ja");
        expect(result.language.translated).toBe("zh"); // inherited
    });

    it("should override both language fields", () => {
        const perVideo: PerVideoConfig = {
            language: { original: "ja", translated: "en" },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.language.original).toBe("ja");
        expect(result.language.translated).toBe("en");
    });

    // ── AI Settings ─────────────────────────────────────────

    it("should override AI model fields", () => {
        const perVideo: PerVideoConfig = {
            ai: { llmModel: "claude-sonnet-4-20250514" },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.ai.llmModel).toBe("claude-sonnet-4-20250514");
        expect(result.ai.ttsModel).toBeNull(); // inherited
        expect(result.ai.prompts).toEqual({}); // inherited
    });

    it("should merge prompts at key level", () => {
        const globalWithPrompts: GlobalSettings = {
            ...global,
            ai: {
                llmModel: null,
                ttsModel: null,
                prompts: {
                    timeline: "default_v1",
                    quiz: "default_v1",
                    note: "default_v1",
                },
            },
        };

        const perVideo: PerVideoConfig = {
            ai: {
                prompts: { quiz: "concise_v2" },
            },
        };

        const result = resolveSettings(globalWithPrompts, perVideo);

        expect(result.ai.prompts).toEqual({
            timeline: "default_v1",
            quiz: "concise_v2",
            note: "default_v1",
        });
    });

    // ── Playback Settings ───────────────────────────────────

    it("should override playback fields", () => {
        const perVideo: PerVideoConfig = {
            playback: { autoPauseOnLeave: true, subtitleRepeatCount: 3 },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.playback.autoPauseOnLeave).toBe(true);
        expect(result.playback.subtitleRepeatCount).toBe(3);
        // inherited
        expect(result.playback.autoResumeOnReturn).toBe(global.playback.autoResumeOnReturn);
        expect(result.playback.voiceoverAutoSwitchThresholdMs).toBe(global.playback.voiceoverAutoSwitchThresholdMs);
    });

    // ── Subtitle Display ────────────────────────────────────

    it("should override subtitle display fields", () => {
        const perVideo: PerVideoConfig = {
            subtitleDisplay: { fontSize: 24 },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.subtitleDisplay.fontSize).toBe(24);
        expect(result.subtitleDisplay.bottomOffset).toBe(global.subtitleDisplay.bottomOffset);
    });

    // ── Notifications ───────────────────────────────────────

    it("should override notification fields", () => {
        const perVideo: PerVideoConfig = {
            notifications: { browserNotificationsEnabled: true },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.notifications.browserNotificationsEnabled).toBe(true);
        expect(result.notifications.toastNotificationsEnabled).toBe(global.notifications.toastNotificationsEnabled);
    });

    // ── Live2D ──────────────────────────────────────────────

    it("should override live2d fields", () => {
        const perVideo: PerVideoConfig = {
            live2d: { enabled: true, modelScale: 2.0 },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.live2d.enabled).toBe(true);
        expect(result.live2d.modelScale).toBe(2.0);
        expect(result.live2d.modelPath).toBe(global.live2d.modelPath);
    });

    // ── Dictionary ──────────────────────────────────────────

    it("should override dictionary fields", () => {
        const perVideo: PerVideoConfig = {
            dictionary: { enabled: false },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.dictionary.enabled).toBe(false);
        expect(result.dictionary.interactionMode).toBe(global.dictionary.interactionMode);
    });

    // ── Standalone fields ───────────────────────────────────

    it("should override standalone fields", () => {
        const perVideo: PerVideoConfig = {
            learnerProfile: "Beginner in linear algebra",
            hideSidebars: true,
            viewMode: "widescreen",
        };
        const result = resolveSettings(global, perVideo);

        expect(result.learnerProfile).toBe("Beginner in linear algebra");
        expect(result.hideSidebars).toBe(true);
        expect(result.viewMode).toBe("widescreen");
    });

    // ── Note Settings ───────────────────────────────────────

    it("should override note settings", () => {
        const perVideo: PerVideoConfig = {
            note: { contextMode: "slide" },
        };
        const result = resolveSettings(global, perVideo);

        expect(result.note.contextMode).toBe("slide");
    });

    // ── Cross-group overrides ───────────────────────────────

    it("should handle overrides across multiple groups", () => {
        const perVideo: PerVideoConfig = {
            language: { original: "ja" },
            ai: { llmModel: "claude-sonnet-4-20250514" },
            playback: { autoPauseOnLeave: true },
            subtitleDisplay: { fontSize: 20 },
            learnerProfile: "Advanced CS",
        };
        const result = resolveSettings(global, perVideo);

        expect(result.language.original).toBe("ja");
        expect(result.language.translated).toBe("zh"); // inherited
        expect(result.ai.llmModel).toBe("claude-sonnet-4-20250514");
        expect(result.playback.autoPauseOnLeave).toBe(true);
        expect(result.playback.autoResumeOnReturn).toBe(false); // inherited
        expect(result.subtitleDisplay.fontSize).toBe(20);
        expect(result.learnerProfile).toBe("Advanced CS");
        // Unmodified groups fully inherited
        expect(result.notifications).toEqual(global.notifications);
        expect(result.dictionary).toEqual(global.dictionary);
    });

    // ── Global settings not mutated ─────────────────────────

    it("should not mutate the global settings object", () => {
        const globalCopy = JSON.parse(JSON.stringify(global));
        const perVideo: PerVideoConfig = {
            playback: { autoPauseOnLeave: true },
            ai: { prompts: { custom: "test" } },
        };
        resolveSettings(global, perVideo);

        expect(JSON.parse(JSON.stringify(global))).toEqual(globalCopy);
    });
});

describe("toTaskConfig", () => {
    it("should extract flat task config from resolved settings", () => {
        const resolved: GlobalSettings = {
            ...DEFAULT_GLOBAL_SETTINGS,
            language: { original: "ja", translated: "en" },
            ai: { llmModel: "gpt-4o", ttsModel: "alloy", prompts: { quiz: "v2" } },
            learnerProfile: "Expert",
            note: { contextMode: "slide" },
        };
        const task = toTaskConfig(resolved);

        expect(task.sourceLanguage).toBe("ja");
        expect(task.targetLanguage).toBe("en");
        expect(task.llmModel).toBe("gpt-4o");
        expect(task.ttsModel).toBe("alloy");
        expect(task.prompts).toEqual({ quiz: "v2" });
        expect(task.learnerProfile).toBe("Expert");
        expect(task.noteContextMode).toBe("slide");
    });
});

describe("isFieldOverridden", () => {
    it("should return false for null config", () => {
        expect(isFieldOverridden(null, "playback.autoPauseOnLeave")).toBe(false);
    });

    it("should return false for unset field", () => {
        const perVideo: PerVideoConfig = { language: { original: "ja" } };
        expect(isFieldOverridden(perVideo, "playback.autoPauseOnLeave")).toBe(false);
    });

    it("should return true for set nested field", () => {
        const perVideo: PerVideoConfig = { playback: { autoPauseOnLeave: true } };
        expect(isFieldOverridden(perVideo, "playback.autoPauseOnLeave")).toBe(true);
    });

    it("should return true for set standalone field", () => {
        const perVideo: PerVideoConfig = { learnerProfile: "test" };
        expect(isFieldOverridden(perVideo, "learnerProfile")).toBe(true);
    });

    it("should return true for false boolean values", () => {
        const perVideo: PerVideoConfig = { playback: { autoPauseOnLeave: false } };
        expect(isFieldOverridden(perVideo, "playback.autoPauseOnLeave")).toBe(true);
    });
});

describe("countOverrides", () => {
    it("should return 0 for null config", () => {
        expect(countOverrides(null)).toBe(0);
    });

    it("should count leaf fields", () => {
        const perVideo: PerVideoConfig = {
            language: { original: "ja" },
            playback: { autoPauseOnLeave: true, subtitleRepeatCount: 3 },
            learnerProfile: "test",
        };
        expect(countOverrides(perVideo)).toBe(4);
    });

    it("should count prompts as 1", () => {
        const perVideo: PerVideoConfig = {
            ai: { prompts: { quiz: "v2", note: "v3" } },
        };
        expect(countOverrides(perVideo)).toBe(1);
    });
});

describe("setOverrideField", () => {
    it("should set a standalone field", () => {
        const result = setOverrideField({}, "learnerProfile", "test");
        expect(result).toEqual({ learnerProfile: "test" });
    });

    it("should set a nested field", () => {
        const result = setOverrideField({}, "playback.autoPauseOnLeave", true);
        expect(result).toEqual({ playback: { autoPauseOnLeave: true } });
    });

    it("should preserve other fields", () => {
        const initial: PerVideoConfig = {
            playback: { autoPauseOnLeave: true },
            learnerProfile: "test",
        };
        const result = setOverrideField(initial, "playback.subtitleRepeatCount", 3);
        expect(result).toEqual({
            playback: { autoPauseOnLeave: true, subtitleRepeatCount: 3 },
            learnerProfile: "test",
        });
    });
});

describe("clearOverrideField", () => {
    it("should remove a standalone field", () => {
        const initial: PerVideoConfig = { learnerProfile: "test", hideSidebars: true };
        const result = clearOverrideField(initial, "learnerProfile");
        expect(result).toEqual({ hideSidebars: true });
    });

    it("should remove a nested field and clean up empty parent", () => {
        const initial: PerVideoConfig = { playback: { autoPauseOnLeave: true } };
        const result = clearOverrideField(initial, "playback.autoPauseOnLeave");
        expect(result).toEqual({});
    });

    it("should remove a nested field but keep sibling", () => {
        const initial: PerVideoConfig = {
            playback: { autoPauseOnLeave: true, subtitleRepeatCount: 3 },
        };
        const result = clearOverrideField(initial, "playback.autoPauseOnLeave");
        expect(result).toEqual({ playback: { subtitleRepeatCount: 3 } });
    });
});
