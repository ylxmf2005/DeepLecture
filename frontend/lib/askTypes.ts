export type AskContextTimelineItem = {
    type: "timeline";
    id: string;
    title: string;
    content: string;
    start: number;
    end: number;
};

export type AskContextScreenshotItem = {
    type: "screenshot";
    id: string;
    imageUrl: string;
    timestamp: number;
    /**
     * Optional absolute image path on the backend.
     * When present, the server can pass the actual frame
     * to a vision-capable LLM instead of relying only on text.
     */
    imagePath?: string;
};

export type AskContextSubtitleItem = {
    type: "subtitle";
    id: string;
    text: string;
    startTime: number;
};

export type AskContextItem =
    | AskContextTimelineItem
    | AskContextScreenshotItem
    | AskContextSubtitleItem;

export interface AskMessage {
    role: "user" | "assistant";
    content: string;
}

