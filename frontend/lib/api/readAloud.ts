/**
 * Read-Aloud APIs — SSE streaming + REST audio fetch for sentence-by-sentence TTS playback.
 *
 * Unlike task-based generation (podcast, cheatsheet), read-aloud uses a dedicated SSE channel
 * that pushes real-time signals as each sentence is synthesized. The frontend then fetches
 * individual sentence MP3 files via REST.
 */

import { api, API_BASE_URL } from "./client";

// ─── SSE Event Types ─────────────────────────────────────────

export interface ReadAloudMeta {
    sessionId: string;
    totalParagraphs: number;
    totalSentences: number;
    paragraphs: Array<{
        index: number;
        title: string | null;
        sentenceCount: number;
    }>;
}

export interface SentenceReady {
    sessionId: string;
    variantKey: string;
    paragraphIndex: number;
    sentenceIndex: number;
    sentenceKey: string;
    originalText: string;
    spokenText: string;
    cached?: boolean;
}

export interface ParagraphStart {
    paragraphIndex: number;
    title: string | null;
    sentenceCount: number;
}

export interface ReadAloudComplete {
    sessionId: string;
    totalParagraphs: number;
    totalSentences: number;
    totalErrors: number;
    cancelled?: boolean;
}

export interface ReadAloudError {
    error: string;
}

// ─── SSE Connection ──────────────────────────────────────────

export interface ReadAloudStreamParams {
    contentId: string;
    targetLanguage: string;
    sourceLanguage?: string;
    ttsModel?: string;
    startParagraph?: number;
}

/**
 * Create an EventSource for the read-aloud SSE stream.
 * The backend pushes events as each sentence is synthesized:
 *   read_aloud_meta → paragraph_start → sentence_ready* → paragraph_end → ... → read_aloud_complete
 */
export function createReadAloudEventSource(params: ReadAloudStreamParams): EventSource {
    const url = new URL(
        `${API_BASE_URL}/api/read-aloud/stream/${encodeURIComponent(params.contentId)}`
    );

    url.searchParams.set("target_language", params.targetLanguage);

    if (params.sourceLanguage) {
        url.searchParams.set("source_language", params.sourceLanguage);
    }
    if (params.ttsModel) {
        url.searchParams.set("tts_model", params.ttsModel);
    }
    if (params.startParagraph !== undefined && params.startParagraph > 0) {
        url.searchParams.set("start_paragraph", String(params.startParagraph));
    }

    return new EventSource(url.toString());
}

// ─── REST Audio Fetch ────────────────────────────────────────

/**
 * Build the URL for fetching a single sentence's MP3 audio.
 */
export function getSentenceAudioUrl(contentId: string, sentenceKey: string, variantKey: string): string {
    const url = new URL(
        `${API_BASE_URL}/api/read-aloud/audio/${encodeURIComponent(contentId)}/${encodeURIComponent(sentenceKey)}`
    );
    url.searchParams.set("variant_key", variantKey);
    return url.toString();
}

/**
 * Request cancellation for an active read-aloud session.
 */
export async function cancelReadAloud(contentId: string, sessionId: string): Promise<void> {
    await api.post(`/read-aloud/cancel/${encodeURIComponent(contentId)}`, {
        sessionId,
    });
}
