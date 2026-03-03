"use client";

import { useCallback, useMemo, useState } from "react";
import {
    AlertCircle,
    BookCheck,
    ChevronDown,
    ChevronUp,
    ExternalLink,
    Loader2,
    RefreshCw,
    Sparkles,
} from "lucide-react";
import { getTestPaper, generateTestPaper } from "@/lib/api/test-paper";
import type { TestQuestion } from "@/lib/api/test-paper";
import { useLanguageSettings, useNoteSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import { useSSEGenerationRetry } from "@/hooks/useSSEGenerationRetry";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/timeFormat";

const log = logger.scope("TestTab");

interface TestTabProps {
    videoId: string;
    onSeek: (time: number) => void;
    refreshTrigger: number;
}

interface TestPaperData {
    questions: TestQuestion[];
    updatedAt: string | null;
}

const BLOOM_LEVEL_STYLES: Record<string, string> = {
    remember: "bg-gray-100 text-gray-700 dark:bg-gray-800/70 dark:text-gray-300",
    understand: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
    apply: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
    analyze: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    evaluate: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
    create: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
};

function humanize(value: string): string {
    return value
        .split("_")
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

export function TestTab({ videoId, onSeek, refreshTrigger }: TestTabProps) {
    const { translated: language } = useLanguageSettings();
    const noteSettings = useNoteSettings();
    const [expanded, setExpanded] = useState<Record<number, boolean>>({});

    const fetchContent = useCallback(async (): Promise<TestPaperData | null> => {
        const result = await getTestPaper(videoId, language || "en");
        if (result && result.questions.length > 0) {
            return { questions: result.questions, updatedAt: result.updatedAt };
        }
        return null;
    }, [videoId, language]);

    const submitGeneration = useCallback(async () => {
        return await generateTestPaper({
            contentId: videoId,
            language: language || "en",
            contextMode: noteSettings.contextMode,
            minCriticality: "medium",
            subjectType: "auto",
        });
    }, [videoId, language, noteSettings.contextMode]);

    const { data, loading, loadError, isGenerating, clearError, handleGenerate } =
        useSSEGenerationRetry<TestPaperData>({
            contentId: videoId,
            refreshTrigger,
            fetchContent,
            submitGeneration,
            log,
            extraDeps: [language],
            taskType: "test_paper_generation",
        });

    const questions = useMemo(() => data?.questions ?? [], [data?.questions]);
    const updatedAt = data?.updatedAt ?? null;
    const hasContent = questions.length > 0;
    const hasError = loadError !== null;

    const toggleExpanded = useCallback((index: number) => {
        setExpanded((prev) => ({ ...prev, [index]: !prev[index] }));
    }, []);

    const handleGenerateAndCollapse = useCallback(() => {
        setExpanded({});
        handleGenerate();
    }, [handleGenerate]);

    const questionTypeSummary = useMemo(() => {
        const counts: Record<string, number> = {};
        for (const question of questions) {
            const key = question.questionType || "unknown";
            counts[key] = (counts[key] || 0) + 1;
        }
        return Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([kind, count]) => `${humanize(kind)} × ${count}`)
            .join(" · ");
    }, [questions]);

    if (loading && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
                <p className="text-sm text-muted-foreground">Loading test paper...</p>
            </div>
        );
    }

    if (isGenerating) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <Loader2 className="w-12 h-12 text-emerald-600 animate-spin" />
                <div className="space-y-2">
                    <p className="text-foreground font-medium">Generating test paper...</p>
                    <p className="text-sm text-muted-foreground max-w-xs">
                        Creating exam-style open-ended questions with reference answers and scoring criteria.
                    </p>
                </div>
            </div>
        );
    }

    if (hasError && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
                <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-full">
                    <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
                </div>
                <p className="text-foreground font-medium">Error</p>
                <p className="text-sm text-muted-foreground max-w-xs">{loadError}</p>
                <button
                    onClick={clearError}
                    className="text-sm text-emerald-600 dark:text-emerald-400 hover:underline"
                >
                    Dismiss
                </button>
            </div>
        );
    }

    if (!hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="bg-emerald-50 dark:bg-emerald-900/20 p-6 rounded-full">
                    <BookCheck className="w-12 h-12 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="max-w-xs space-y-2">
                    <h3 className="text-lg font-semibold text-foreground">Test Paper</h3>
                    <p className="text-sm text-muted-foreground">
                        Generate exam-style open-ended questions for deep review, each with reference answers and scoring points.
                    </p>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50"
                >
                    <Sparkles className="w-4 h-4" />
                    Generate Test Paper
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-background">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
                <div className="flex items-center gap-2 min-w-0">
                    <BookCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    <h3 className="font-semibold text-foreground">Test Paper</h3>
                    <span className="text-xs text-muted-foreground">{questions.length} questions</span>
                    {questionTypeSummary && (
                        <span className="text-xs text-muted-foreground truncate max-w-[280px]">
                            · {questionTypeSummary}
                        </span>
                    )}
                    {updatedAt && (
                        <span className="text-xs text-muted-foreground">· {new Date(updatedAt).toLocaleDateString()}</span>
                    )}
                </div>
                <button
                    onClick={handleGenerateAndCollapse}
                    disabled={isGenerating}
                    className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-50"
                    title="Regenerate"
                >
                    <RefreshCw className="w-4 h-4 text-muted-foreground" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {questions.map((question, index) => {
                    const isOpen = !!expanded[index];
                    const bloomKey = (question.bloomLevel || "").toLowerCase();
                    const bloomStyle = BLOOM_LEVEL_STYLES[bloomKey] || BLOOM_LEVEL_STYLES.remember;

                    return (
                        <article key={index} className="rounded-lg border border-border bg-card p-4 space-y-3">
                            <div className="flex items-start gap-2">
                                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 text-xs font-bold flex items-center justify-center">
                                    {index + 1}
                                </span>

                                <div className="flex-1 min-w-0 space-y-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="px-2 py-1 rounded-md text-[11px] font-medium bg-slate-100 text-slate-700 dark:bg-slate-800/80 dark:text-slate-300">
                                            {humanize(question.questionType || "question")}
                                        </span>
                                        <span className={cn("px-2 py-1 rounded-md text-[11px] font-medium", bloomStyle)}>
                                            {humanize(bloomKey || "remember")}
                                        </span>
                                        {typeof question.sourceTimestamp === "number" && (
                                            <button
                                                onClick={() => onSeek(question.sourceTimestamp ?? 0)}
                                                className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-300 dark:hover:bg-emerald-900/35"
                                            >
                                                <ExternalLink className="w-3 h-3" />
                                                {formatTime(question.sourceTimestamp)}
                                            </button>
                                        )}
                                    </div>

                                    <p className="text-sm font-medium text-foreground leading-relaxed">{question.stem}</p>
                                </div>
                            </div>

                            <div className="ml-8">
                                <button
                                    onClick={() => toggleExpanded(index)}
                                    aria-expanded={isOpen}
                                    className="w-full inline-flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/60 transition-colors"
                                >
                                    <span>{isOpen ? "Hide reference answer & scoring" : "Show reference answer & scoring"}</span>
                                    {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </button>

                                {isOpen && (
                                    <div className="mt-3 space-y-3 rounded-md border border-border bg-muted/30 p-3">
                                        <div className="space-y-1">
                                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Reference Answer</p>
                                            <p className="text-sm text-foreground leading-relaxed">{question.referenceAnswer}</p>
                                        </div>

                                        <div className="space-y-1">
                                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Scoring Criteria</p>
                                            <ul className="list-disc pl-5 space-y-1">
                                                {question.scoringCriteria.map((point, pointIndex) => (
                                                    <li key={pointIndex} className="text-sm text-foreground leading-relaxed">
                                                        {point}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </article>
                    );
                })}
            </div>
        </div>
    );
}
