import { describe, expect, it } from "vitest";
import { normalizeConfigPayload, serializeConfigPayload } from "@/lib/api/configSerialization";

describe("configSerialization", () => {
    it("normalizes snake_case AI payloads from backend", () => {
        const normalized = normalizeConfigPayload({
            ai: {
                llm_model: "cch",
                tts_model: "fishaudio-elaina",
                llm: {
                    task_models: {
                        ask_video: "gemini",
                    },
                },
                tts: {
                    task_models: {
                        voiceover_generation: "edge-default",
                    },
                },
            },
        });

        expect(normalized.ai).toEqual({
            llmModel: "cch",
            ttsModel: "fishaudio-elaina",
            llmTaskModels: {
                ask_video: "gemini",
            },
            ttsTaskModels: {
                voiceover_generation: "edge-default",
            },
        });
    });

    it("normalizes camelCase AI payloads for compatibility", () => {
        const normalized = normalizeConfigPayload({
            ai: {
                llmModel: "cch",
                ttsModel: "fishaudio-elaina",
                llm: {
                    taskModels: {
                        ask_video: "gemini",
                    },
                },
                tts: {
                    taskModels: {
                        voiceover_generation: "edge-default",
                    },
                },
            },
        });

        expect(normalized.ai).toEqual({
            llmModel: "cch",
            ttsModel: "fishaudio-elaina",
            llmTaskModels: {
                ask_video: "gemini",
            },
            ttsTaskModels: {
                voiceover_generation: "edge-default",
            },
        });
    });

    it("serializes AI settings to backend snake_case contract", () => {
        const serialized = serializeConfigPayload({
            ai: {
                llmModel: "cch",
                ttsModel: "fishaudio-elaina",
                llmTaskModels: {
                    ask_video: "gemini",
                    note_generation: null,
                },
                ttsTaskModels: {
                    voiceover_generation: "edge-default",
                },
            },
        });

        expect(serialized).toEqual({
            ai: {
                llm_model: "cch",
                tts_model: "fishaudio-elaina",
                llm: {
                    task_models: {
                        ask_video: "gemini",
                    },
                },
                tts: {
                    task_models: {
                        voiceover_generation: "edge-default",
                    },
                },
            },
        });
    });
});
