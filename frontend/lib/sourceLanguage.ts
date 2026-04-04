import { AUTO_LANGUAGE } from "./languages";

function normalizeLanguage(value: string | null | undefined): string | null {
    const normalized = value?.trim().toLowerCase() ?? "";
    return normalized || null;
}

export function isAutoSourceLanguage(value: string | null | undefined): boolean {
    return normalizeLanguage(value) === AUTO_LANGUAGE;
}

export function resolveConfiguredSourceLanguage(
    configuredLanguage: string | null | undefined,
    detectedSourceLanguage: string | null | undefined
): string | null {
    const configured = normalizeLanguage(configuredLanguage);
    if (!configured) return null;
    if (configured !== AUTO_LANGUAGE) return configured;
    return normalizeLanguage(detectedSourceLanguage);
}

export function isUnresolvedAutoSourceLanguage(
    configuredLanguage: string | null | undefined,
    detectedSourceLanguage: string | null | undefined
): boolean {
    return isAutoSourceLanguage(configuredLanguage) &&
        resolveConfiguredSourceLanguage(configuredLanguage, detectedSourceLanguage) === null;
}
