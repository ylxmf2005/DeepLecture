import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_GLOBAL_SETTINGS } from "@/stores/types";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import {
    getAIOverrides,
    getLLMOverrides,
    getTTSOverrides,
    setCurrentVideoConfig,
    withAIOverrides,
    withLLMOverrides,
    withTTSOverrides,
} from "@/lib/api/ai-overrides";

describe("ai-overrides", () => {
    afterEach(() => {
        setCurrentVideoConfig(null);
        useGlobalSettingsStore.setState({
            ...DEFAULT_GLOBAL_SETTINGS,
            _hydrated: true,
            _languageLoading: false,
        });
    });

    it("merges prompts without injecting model IDs", () => {
        useGlobalSettingsStore.setState({
            ai: {
                ...DEFAULT_GLOBAL_SETTINGS.ai,
                llmModel: "global-llm",
                ttsModel: "global-tts",
                prompts: {
                    ask_video: "ask-default",
                },
            },
        });

        setCurrentVideoConfig({
            ai: {
                llmModel: "video-llm",
                ttsModel: "video-tts",
                prompts: {
                    note_generation: "note-video",
                },
            },
        });

        expect(getAIOverrides()).toEqual({
            prompts: {
                ask_video: "ask-default",
                note_generation: "note-video",
            },
        });
        expect(getLLMOverrides()).toEqual({
            prompts: {
                ask_video: "ask-default",
                note_generation: "note-video",
            },
        });
        expect(getTTSOverrides()).toEqual({});
    });

    it("keeps explicit request-time llm_model override in payload", () => {
        useGlobalSettingsStore.setState({
            ai: {
                ...DEFAULT_GLOBAL_SETTINGS.ai,
                prompts: { ask_video: "ask-default" },
            },
        });
        setCurrentVideoConfig({
            ai: {
                prompts: { note_generation: "note-video" },
            },
        });

        const payload = withLLMOverrides({
            content_id: "c1",
            llm_model: "request-llm",
        });

        expect(payload.llm_model).toBe("request-llm");
        expect(payload.prompts).toEqual({
            ask_video: "ask-default",
            note_generation: "note-video",
        });
    });

    it("keeps explicit request-time tts_model override in payload", () => {
        const payload = withTTSOverrides({
            content_id: "c1",
            tts_model: "request-tts",
        });

        expect(payload.tts_model).toBe("request-tts");
    });

    it("keeps explicit request-time llm/tts overrides in combined payload", () => {
        useGlobalSettingsStore.setState({
            ai: {
                ...DEFAULT_GLOBAL_SETTINGS.ai,
                prompts: { timeline_generation: "timeline-default" },
            },
        });

        const payload = withAIOverrides({
            content_id: "c1",
            llm_model: "request-llm",
            tts_model: "request-tts",
        });

        expect(payload.llm_model).toBe("request-llm");
        expect(payload.tts_model).toBe("request-tts");
        expect(payload.prompts).toEqual({ timeline_generation: "timeline-default" });
    });
});
