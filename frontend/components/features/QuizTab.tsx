"use client";

import { useState, useCallback } from "react";
import { HelpCircle, RefreshCw, AlertCircle, Loader2, Sparkles, CheckCircle2, XCircle } from "lucide-react";
import { getQuiz, generateQuiz } from "@/lib/api/quiz";
import type { QuizItem } from "@/lib/api/quiz";
import { useLanguageSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import { useSSEGenerationRetry } from "@/hooks/useSSEGenerationRetry";

const log = logger.scope("QuizTab");

interface QuizTabProps {
    videoId: string;
    onSeek: (time: number) => void;
    refreshTrigger: number;
}

interface QuizData {
    items: QuizItem[];
    updatedAt: string | null;
}

/** Tracks per-question answer state */
interface AnswerState {
    selectedIndex: number;
    isCorrect: boolean;
}

export function QuizTab({ videoId, onSeek, refreshTrigger }: QuizTabProps) {
    const { translated: language } = useLanguageSettings();
    const [answers, setAnswers] = useState<Record<number, AnswerState>>({});

    const fetchContent = useCallback(async (): Promise<QuizData | null> => {
        const result = await getQuiz(videoId, language || "en");
        if (result && result.items.length > 0) {
            return { items: result.items, updatedAt: result.updatedAt };
        }
        return null;
    }, [videoId, language]);

    const submitGeneration = useCallback(async () => {
        return await generateQuiz({
            contentId: videoId,
            language: language || "en",
            questionCount: 5,
            contextMode: "auto",
            minCriticality: "medium",
            subjectType: "auto",
        });
    }, [videoId, language]);

    const { data, loading, loadError, isGenerating, clearError, handleGenerate } =
        useSSEGenerationRetry<QuizData>({
            contentId: videoId,
            refreshTrigger,
            fetchContent,
            submitGeneration,
            log,
            extraDeps: [language],
            taskType: "quiz_generation",
        });

    const items = data?.items ?? [];
    const updatedAt = data?.updatedAt ?? null;

    const handleSelectOption = useCallback((questionIndex: number, optionIndex: number, correctIndex: number) => {
        setAnswers((prev) => {
            if (prev[questionIndex]) return prev; // Already answered
            return {
                ...prev,
                [questionIndex]: {
                    selectedIndex: optionIndex,
                    isCorrect: optionIndex === correctIndex,
                },
            };
        });
    }, []);

    const handleReset = useCallback(() => {
        setAnswers({});
    }, []);

    const hasContent = items.length > 0;
    const hasError = loadError !== null;
    const answeredCount = Object.keys(answers).length;
    const correctCount = Object.values(answers).filter((a) => a.isCorrect).length;

    // Loading state
    if (loading && !hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <Loader2 className="w-8 h-8 text-violet-600 animate-spin" />
                <p className="text-sm text-muted-foreground">Loading quiz...</p>
            </div>
        );
    }

    // Generating state
    if (isGenerating) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="relative">
                    <Loader2 className="w-12 h-12 text-violet-600 animate-spin" />
                </div>
                <div className="space-y-2">
                    <p className="text-foreground font-medium">Generating quiz...</p>
                    <p className="text-sm text-muted-foreground max-w-xs">
                        Creating multiple-choice questions from lecture content.
                    </p>
                </div>
            </div>
        );
    }

    // Error state
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
                    className="text-sm text-violet-600 dark:text-violet-400 hover:underline"
                >
                    Dismiss
                </button>
            </div>
        );
    }

    // Idle state - no content yet
    if (!hasContent) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="bg-violet-50 dark:bg-violet-900/20 p-6 rounded-full">
                    <HelpCircle className="w-12 h-12 text-violet-600 dark:text-violet-400" />
                </div>
                <div className="max-w-xs space-y-2">
                    <h3 className="text-lg font-semibold text-foreground">Quiz</h3>
                    <p className="text-sm text-muted-foreground">
                        Generate multiple-choice questions to test your understanding of the lecture content.
                    </p>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50"
                >
                    <Sparkles className="w-4 h-4" />
                    Generate Quiz
                </button>
            </div>
        );
    }

    // Content view
    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
                <div className="flex items-center gap-2">
                    <HelpCircle className="w-5 h-5 text-violet-600 dark:text-violet-400" />
                    <h3 className="font-semibold text-foreground">Quiz</h3>
                    {answeredCount > 0 && (
                        <span className="text-xs text-muted-foreground">
                            {correctCount}/{answeredCount} correct
                        </span>
                    )}
                    {updatedAt && (
                        <span className="text-xs text-muted-foreground">
                            Updated {new Date(updatedAt).toLocaleDateString()}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {answeredCount > 0 && (
                        <button
                            onClick={handleReset}
                            className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                            title="Reset answers"
                        >
                            Reset
                        </button>
                    )}
                    <button
                        onClick={handleGenerate}
                        disabled={isGenerating}
                        className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-50"
                        title="Regenerate"
                    >
                        <RefreshCw className="w-4 h-4 text-muted-foreground" />
                    </button>
                </div>
            </div>

            {/* Questions list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {items.map((item, qIndex) => {
                    const answer = answers[qIndex];
                    const isAnswered = !!answer;

                    return (
                        <div key={qIndex} className="rounded-lg border border-border bg-card p-4 space-y-3">
                            {/* Question stem */}
                            <div className="flex gap-2">
                                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 text-xs font-bold flex items-center justify-center">
                                    {qIndex + 1}
                                </span>
                                <p className="text-sm font-medium text-foreground leading-relaxed">{item.stem}</p>
                            </div>

                            {/* Options */}
                            <div className="space-y-2 ml-8">
                                {item.options.map((option, oIndex) => {
                                    const isSelected = isAnswered && answer.selectedIndex === oIndex;
                                    const isCorrectOption = oIndex === item.answerIndex;
                                    const showCorrect = isAnswered && isCorrectOption;
                                    const showWrong = isSelected && !answer.isCorrect;

                                    let optionClasses = "flex items-start gap-2 p-2.5 rounded-md border text-sm transition-colors cursor-pointer ";

                                    if (!isAnswered) {
                                        optionClasses += "border-border hover:border-violet-300 dark:hover:border-violet-600 hover:bg-violet-50 dark:hover:bg-violet-900/10";
                                    } else if (showCorrect) {
                                        optionClasses += "border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/20";
                                    } else if (showWrong) {
                                        optionClasses += "border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20";
                                    } else {
                                        optionClasses += "border-border opacity-60 cursor-default";
                                    }

                                    return (
                                        <button
                                            key={oIndex}
                                            onClick={() => handleSelectOption(qIndex, oIndex, item.answerIndex)}
                                            disabled={isAnswered}
                                            className={optionClasses}
                                        >
                                            <span className="flex-shrink-0 w-5 h-5 rounded-full border border-current text-xs flex items-center justify-center mt-0.5">
                                                {showCorrect && <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />}
                                                {showWrong && <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />}
                                                {!showCorrect && !showWrong && String.fromCharCode(65 + oIndex)}
                                            </span>
                                            <span className="text-left text-foreground">{option}</span>
                                        </button>
                                    );
                                })}
                            </div>

                            {/* Explanation (shown after answering) */}
                            {isAnswered && item.explanation && (
                                <div className="ml-8 mt-2 p-3 rounded-md bg-muted/50 border border-border">
                                    <p className="text-xs font-semibold text-muted-foreground mb-1">Explanation</p>
                                    <p className="text-sm text-foreground leading-relaxed">{item.explanation}</p>
                                </div>
                            )}
                        </div>
                    );
                })}

                {/* Score summary */}
                {answeredCount === items.length && items.length > 0 && (
                    <div className="rounded-lg border border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-900/20 p-4 text-center space-y-2">
                        <p className="text-lg font-bold text-violet-700 dark:text-violet-300">
                            Score: {correctCount}/{items.length}
                        </p>
                        <p className="text-sm text-muted-foreground">
                            {correctCount === items.length
                                ? "Perfect score!"
                                : correctCount >= items.length * 0.7
                                  ? "Great job!"
                                  : "Keep studying and try again."}
                        </p>
                        <button
                            onClick={handleReset}
                            className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium transition-colors"
                        >
                            Try Again
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
