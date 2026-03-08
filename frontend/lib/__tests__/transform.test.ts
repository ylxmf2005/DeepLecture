import { describe, expect, it } from "vitest";
import { unwrapApiResponse } from "@/lib/api/transform";

describe("API transform", () => {
    it("preserves identifier map keys for prompts while camelizing schema fields", () => {
        const raw = {
            success: true,
            data: {
                prompts: {
                    ask_video: {
                        default_impl_id: "default",
                        options: [{ id: "default", is_default: true }],
                    },
                    timeline_segmentation: {
                        default_impl_id: "default",
                        options: [{ id: "default", is_default: true }],
                    },
                },
            },
        };

        const unwrapped = unwrapApiResponse<{
            prompts: Record<string, { defaultImplId: string; options: Array<{ isDefault: boolean }> }>;
        }>(raw);

        expect(Object.keys(unwrapped.prompts)).toEqual(
            expect.arrayContaining(["ask_video", "timeline_segmentation"]),
        );
        expect(unwrapped.prompts.ask_video.defaultImplId).toBe("default");
        expect(unwrapped.prompts.timeline_segmentation.options[0].isDefault).toBe(true);
    });

    it("preserves identifier map keys for task defaults and metadata descriptions", () => {
        const raw = {
            success: true,
            data: {
                llm: {
                    task_model_defaults: {
                        ask_video: "gpt-5",
                        timeline_generation: "gpt-5-mini",
                    },
                },
                metadata: {
                    ask_video: {
                        allowed: ["history_block"],
                        required: [],
                        descriptions: {
                            history_block: "conversation context",
                        },
                    },
                },
            },
        };

        const unwrapped = unwrapApiResponse<{
            llm: { taskModelDefaults: Record<string, string> };
            metadata: Record<string, { descriptions: Record<string, string> }>;
        }>(raw);

        expect(unwrapped.llm.taskModelDefaults.ask_video).toBe("gpt-5");
        expect(unwrapped.llm.taskModelDefaults.timeline_generation).toBe("gpt-5-mini");
        expect(unwrapped.metadata.ask_video.descriptions.history_block).toBe(
            "conversation context",
        );
    });
});
