import {
    MessageSquare,
    Subtitles,
    Clock,
    Presentation,
    Lightbulb,
    FileText,
    BookOpen,
    GraduationCap,
    Podcast,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface TemplateCategory {
    label: string;
    icon: LucideIcon;
    funcIds: string[];
}

export const TEMPLATE_CATEGORIES: TemplateCategory[] = [
    { label: "Q&A", icon: MessageSquare, funcIds: ["ask_video", "ask_summarize_context"] },
    { label: "Subtitles", icon: Subtitles, funcIds: ["subtitle_background", "subtitle_enhance_translate"] },
    { label: "Timeline", icon: Clock, funcIds: ["timeline_segmentation", "timeline_explanation"] },
    { label: "Slides", icon: Presentation, funcIds: ["slide_lecture"] },
    { label: "Explanation", icon: Lightbulb, funcIds: ["explanation_system", "explanation_user"] },
    { label: "Notes", icon: FileText, funcIds: ["note_outline", "note_part"] },
    { label: "Knowledge", icon: BookOpen, funcIds: ["cheatsheet_extraction", "cheatsheet_rendering"] },
    { label: "Assessment", icon: GraduationCap, funcIds: ["quiz_generation", "flashcard_generation", "test_paper_generation"] },
    { label: "Podcast", icon: Podcast, funcIds: ["podcast_dialogue", "podcast_dramatize"] },
];

/** Human-readable labels for func_ids (pure display concern). */
export const FUNC_ID_LABELS: Record<string, { label: string; desc: string }> = {
    ask_video: { label: "Video Q&A", desc: "Answer questions about video content" },
    ask_summarize_context: { label: "Context Summary", desc: "Summarize video context" },
    note_outline: { label: "Note Outline", desc: "Generate note structure" },
    note_part: { label: "Note Content", desc: "Generate note sections" },
    timeline_segmentation: { label: "Timeline Segmentation", desc: "Divide video into segments" },
    timeline_explanation: { label: "Timeline Explanation", desc: "Explain timeline segments" },
    subtitle_background: { label: "Subtitle Background", desc: "Generate background context" },
    subtitle_enhance_translate: { label: "Subtitle Enhancement", desc: "Enhance and translate subtitles" },
    explanation_system: { label: "Explanation System", desc: "System prompt for explanations" },
    explanation_user: { label: "Explanation User", desc: "User prompt for explanations" },
    slide_lecture: { label: "Slide Lecture", desc: "Generate lecture from slides" },
    cheatsheet_extraction: { label: "Cheatsheet Extraction", desc: "Extract key knowledge for cheatsheets" },
    cheatsheet_rendering: { label: "Cheatsheet Rendering", desc: "Render cheatsheet layout" },
    quiz_generation: { label: "Quiz Generation", desc: "Generate quiz questions" },
    flashcard_generation: { label: "Flashcard Generation", desc: "Generate active-recall flashcards" },
    test_paper_generation: { label: "Test Paper Generation", desc: "Generate exam-style open-ended questions" },
    podcast_dialogue: { label: "Podcast Dialogue", desc: "Generate two-person podcast dialogue" },
    podcast_dramatize: { label: "Podcast Dramatization", desc: "Rewrite dialogue for natural TTS" },
};

export type DrawerMode = "create" | "edit" | "duplicate";

export interface DrawerState {
    open: boolean;
    mode: DrawerMode;
    funcId: string;
    /** Source template for edit/duplicate. Null for create (uses default). */
    sourceTemplate: {
        implId: string;
        name: string;
        description: string | null;
        systemTemplate: string;
        userTemplate: string;
    } | null;
}

export const INITIAL_DRAWER_STATE: DrawerState = {
    open: false,
    mode: "create",
    funcId: "",
    sourceTemplate: null,
};
