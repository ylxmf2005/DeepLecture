export interface OperationNotificationLabel {
    success: string;
    error: string;
}

export const OPERATION_LABELS: Record<string, OperationNotificationLabel> = {
    content_delete: {
        success: "Content deleted",
        error: "Content delete failed",
    },
    content_rename: {
        success: "Content renamed",
        error: "Content rename failed",
    },
    conversation_delete: {
        success: "Conversation deleted",
        error: "Conversation delete failed",
    },
    conversation_load: {
        success: "Conversation loaded",
        error: "Conversation load failed",
    },
    conversation_create: {
        success: "Conversation created",
        error: "Conversation create failed",
    },
    conversation_message: {
        success: "Message sent",
        error: "Message send failed",
    },
    explanation_delete: {
        success: "Screenshot deleted",
        error: "Screenshot delete failed",
    },
    explanation_load: {
        success: "Screenshots loaded",
        error: "Screenshots load failed",
    },
    note_editor_unavailable: {
        success: "Notes editor is ready",
        error: "Notes editor is not ready",
    },
    note_load: {
        success: "Note loaded",
        error: "Note load failed",
    },
    note_save: {
        success: "Note saved",
        error: "Note save failed",
    },
    note_local_fallback: {
        success: "Note saved locally",
        error: "Note local save failed",
    },
    slide_explain: {
        success: "Slide explanation started",
        error: "Slide explanation failed",
    },
    slide_upload: {
        success: "Slide deck uploaded",
        error: "Slide deck upload failed",
    },
    subtitle_load: {
        success: "Subtitles loaded",
        error: "Subtitle load failed",
    },
    voiceover_delete: {
        success: "Voiceover deleted",
        error: "Voiceover delete failed",
    },
    voiceover_refresh: {
        success: "Voiceovers refreshed",
        error: "Voiceover refresh failed",
    },
    voiceover_rename: {
        success: "Voiceover renamed",
        error: "Voiceover rename failed",
    },
    voiceover_name_required: {
        success: "Voiceover name set",
        error: "Voiceover name is required",
    },
    voiceover_quick_toggle_preset: {
        success: "Quick toggle preset ready",
        error: "Set quick toggle presets first",
    },
};

function humanizeOperation(operation: string): string {
    return operation
        .split("_")
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

/** Get labels for non-task operation notifications, with fallback for unknown operations. */
export function getOperationNotificationLabel(operation: string): OperationNotificationLabel {
    const known = OPERATION_LABELS[operation];
    if (known) {
        return known;
    }

    const readable = humanizeOperation(operation);
    if (!readable) {
        return {
            success: "Operation completed",
            error: "Operation failed",
        };
    }

    return {
        success: `${readable} completed`,
        error: `${readable} failed`,
    };
}
