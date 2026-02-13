import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_GLOBAL_SETTINGS } from "@/stores/types";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import { setCurrentVideoConfig } from "@/lib/api/ai-overrides";
import { generateTimeline } from "@/lib/api/timeline";
import { generateVoiceover } from "@/lib/api/voiceover";
import { generateSlideLecture } from "@/lib/api/content";

vi.mock("@/lib/api/client", () => ({
    api: {
        get: vi.fn(),
        post: vi.fn(),
        delete: vi.fn(),
        patch: vi.fn(),
    },
}));

import { api } from "@/lib/api/client";

describe("API payload overrides", () => {
    beforeEach(() => {
        vi.mocked(api.post).mockReset();
        useGlobalSettingsStore.setState({
            ...DEFAULT_GLOBAL_SETTINGS,
            ai: {
                ...DEFAULT_GLOBAL_SETTINGS.ai,
                llmModel: "global-llm",
                ttsModel: "global-tts",
                prompts: {
                    timeline_generation: "timeline-default",
                },
            },
            _hydrated: true,
            _languageLoading: false,
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
    });

    afterEach(() => {
        setCurrentVideoConfig(null);
    });

    it("does not inject llm_model for LLM tasks by default", async () => {
        vi.mocked(api.post).mockResolvedValue({
            data: { contentId: "c1", taskId: "t1", status: "pending", message: "ok" },
        } as never);

        await generateTimeline("c1", {
            subtitleLanguage: "en",
            outputLanguage: "zh",
        });

        const call = vi.mocked(api.post).mock.calls[0];
        const payload = call[1] as Record<string, unknown>;

        expect(payload.llm_model).toBeUndefined();
        expect(payload.tts_model).toBeUndefined();
        expect(payload.prompts).toEqual({
            timeline_generation: "timeline-default",
            note_generation: "note-video",
        });
    });

    it("does not inject tts_model for TTS tasks by default", async () => {
        vi.mocked(api.post).mockResolvedValue({
            data: { voiceover: { id: "v1" }, message: "ok", taskId: "t2" },
        } as never);

        await generateVoiceover("c1", "original", "voice-1", "en");

        const call = vi.mocked(api.post).mock.calls[0];
        const payload = call[1] as Record<string, unknown>;

        expect(payload.llm_model).toBeUndefined();
        expect(payload.tts_model).toBeUndefined();
    });

    it("does not inject llm_model/tts_model for slide lecture requests", async () => {
        vi.mocked(api.post).mockResolvedValue({
            data: { deckId: "c1", status: "pending", message: "ok", taskId: "t3" },
        } as never);

        await generateSlideLecture("c1", {
            sourceLanguage: "en",
            targetLanguage: "zh",
        });

        const call = vi.mocked(api.post).mock.calls[0];
        const payload = call[1] as Record<string, unknown>;

        expect(payload.llm_model).toBeUndefined();
        expect(payload.tts_model).toBeUndefined();
        expect(payload.prompts).toEqual({
            timeline_generation: "timeline-default",
            note_generation: "note-video",
        });
    });
});
