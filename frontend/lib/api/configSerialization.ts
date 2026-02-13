import type { DeepPartial, GlobalSettings } from "@/stores/types";

type ConfigPayload = DeepPartial<GlobalSettings>;
type AISettingsPayload = Partial<NonNullable<ConfigPayload["ai"]>>;

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toNullableString(value: unknown): string | null | undefined {
    if (value === undefined) return undefined;
    if (value === null) return null;
    if (typeof value !== "string") return undefined;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function normalizeTaskModelMap(value: unknown): Record<string, string> | undefined {
    if (!isRecord(value)) return undefined;

    const output: Record<string, string> = {};
    for (const [taskKey, model] of Object.entries(value)) {
        if (typeof model !== "string") continue;
        const trimmed = model.trim();
        if (trimmed) {
            output[taskKey] = trimmed;
        }
    }

    return Object.keys(output).length > 0 ? output : undefined;
}

function compactTaskModelMap(
    value: Record<string, string | null> | undefined,
): Record<string, string> {
    if (!value) return {};

    const output: Record<string, string> = {};
    for (const [taskKey, model] of Object.entries(value)) {
        if (typeof model !== "string") continue;
        const trimmed = model.trim();
        if (trimmed) {
            output[taskKey] = trimmed;
        }
    }
    return output;
}

function normalizeAISettings(value: unknown): AISettingsPayload | undefined {
    if (!isRecord(value)) return undefined;

    const llmScope = isRecord(value.llm) ? value.llm : undefined;
    const ttsScope = isRecord(value.tts) ? value.tts : undefined;

    const llmModel =
        toNullableString(value.llmModel) ??
        toNullableString(value.llm_model) ??
        toNullableString(llmScope?.defaultModel) ??
        toNullableString(llmScope?.default_model);
    const ttsModel =
        toNullableString(value.ttsModel) ??
        toNullableString(value.tts_model) ??
        toNullableString(ttsScope?.defaultModel) ??
        toNullableString(ttsScope?.default_model);
    const llmTaskModels =
        normalizeTaskModelMap(value.llmTaskModels) ??
        normalizeTaskModelMap(value.llm_task_models) ??
        normalizeTaskModelMap(llmScope?.taskModels) ??
        normalizeTaskModelMap(llmScope?.task_models);
    const ttsTaskModels =
        normalizeTaskModelMap(value.ttsTaskModels) ??
        normalizeTaskModelMap(value.tts_task_models) ??
        normalizeTaskModelMap(ttsScope?.taskModels) ??
        normalizeTaskModelMap(ttsScope?.task_models);

    const prompts = isRecord(value.prompts)
        ? Object.fromEntries(
            Object.entries(value.prompts)
                .filter((entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string")
                .map(([key, promptId]) => [key, promptId.trim()])
                .filter((entry) => entry[1].length > 0),
        )
        : undefined;

    const normalized: AISettingsPayload = {};
    if (llmModel !== undefined) normalized.llmModel = llmModel;
    if (ttsModel !== undefined) normalized.ttsModel = ttsModel;
    if (prompts) normalized.prompts = prompts;
    if (llmTaskModels) normalized.llmTaskModels = llmTaskModels;
    if (ttsTaskModels) normalized.ttsTaskModels = ttsTaskModels;

    return Object.keys(normalized).length > 0 ? normalized : undefined;
}

export function normalizeConfigPayload<T extends ConfigPayload = ConfigPayload>(payload: unknown): T {
    if (!isRecord(payload)) return {} as T;

    const normalized: ConfigPayload = { ...(payload as ConfigPayload) };
    const normalizedAI = normalizeAISettings(payload.ai);

    if (normalizedAI) {
        normalized.ai = normalizedAI as ConfigPayload["ai"];
    }

    return normalized as T;
}

export function serializeConfigPayload(config: unknown): Record<string, unknown> {
    if (!isRecord(config)) return {};

    const payload: Record<string, unknown> = { ...config };
    const ai = isRecord(config.ai) ? config.ai : undefined;

    if (!ai) {
        delete payload.ai;
        return payload;
    }

    const aiPayload: Record<string, unknown> = {};

    if (ai.llmModel !== undefined) aiPayload.llm_model = ai.llmModel;
    if (ai.ttsModel !== undefined) aiPayload.tts_model = ai.ttsModel;
    if (ai.prompts !== undefined) aiPayload.prompts = ai.prompts;

    if (ai.llmTaskModels !== undefined) {
        const llmTaskModels = isRecord(ai.llmTaskModels)
            ? (ai.llmTaskModels as Record<string, string | null>)
            : undefined;
        const currentLlm = isRecord(aiPayload.llm) ? aiPayload.llm : {};
        aiPayload.llm = {
            ...currentLlm,
            task_models: compactTaskModelMap(llmTaskModels),
        };
    }

    if (ai.ttsTaskModels !== undefined) {
        const ttsTaskModels = isRecord(ai.ttsTaskModels)
            ? (ai.ttsTaskModels as Record<string, string | null>)
            : undefined;
        const currentTts = isRecord(aiPayload.tts) ? aiPayload.tts : {};
        aiPayload.tts = {
            ...currentTts,
            task_models: compactTaskModelMap(ttsTaskModels),
        };
    }

    if (Object.keys(aiPayload).length > 0) {
        payload.ai = aiPayload;
    } else {
        delete payload.ai;
    }

    return payload;
}
