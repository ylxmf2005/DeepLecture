"use client";

import { useCallback } from "react";
import { ShieldCheck, RefreshCw, AlertCircle, FileText, Loader2 } from "lucide-react";
import { ClaimCard } from "./ClaimCard";
import { getFactVerificationReport, generateFactVerification } from "@/lib/api";
import { useLanguageSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import { useSSEGenerationRetry } from "@/hooks/useSSEGenerationRetry";
import type { FactVerificationReport } from "@/lib/verifyTypes";

const log = logger.scope("VerifyTab");

interface VerifyTabProps {
    videoId: string;
    onSeek: (time: number) => void;
    refreshTrigger: number;
}

export function VerifyTab({ videoId, onSeek, refreshTrigger }: VerifyTabProps) {
    const { original: language } = useLanguageSettings();

    const fetchContent = useCallback(async (): Promise<FactVerificationReport | null> => {
        return await getFactVerificationReport(videoId, language);
    }, [videoId, language]);

    const submitGeneration = useCallback(async () => {
        return await generateFactVerification({ contentId: videoId, language });
    }, [videoId, language]);

    const { data: report, loading, loadError, isGenerating, clearError, handleGenerate } =
        useSSEGenerationRetry<FactVerificationReport>({
            contentId: videoId,
            refreshTrigger,
            fetchContent,
            submitGeneration,
            log,
            extraDeps: [language],
            taskType: "fact_verification",
        });

    // Determine current state
    const hasReport = report !== null;
    const hasError = loadError !== null;

    // Loading state
    if (loading && !hasReport) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                <p className="text-sm text-muted-foreground">Loading verification report...</p>
            </div>
        );
    }

    // Generating state (task submitted, waiting for completion)
    if (isGenerating) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="relative">
                    <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
                </div>
                <div className="space-y-2">
                    <p className="text-foreground font-medium">Verifying claims...</p>
                    <p className="text-sm text-muted-foreground max-w-xs">
                        Claude is searching the web to verify factual claims. This may take a few minutes.
                    </p>
                </div>
            </div>
        );
    }

    // Error state
    if (hasError && !hasReport) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
                <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-full">
                    <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
                </div>
                <p className="text-foreground font-medium">Error</p>
                <p className="text-sm text-muted-foreground max-w-xs">{loadError}</p>
                <button
                    onClick={clearError}
                    className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                >
                    Dismiss
                </button>
            </div>
        );
    }

    // Idle state - no report yet
    if (!hasReport) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="bg-blue-50 dark:bg-blue-900/20 p-6 rounded-full">
                    <ShieldCheck className="w-12 h-12 text-blue-600 dark:text-blue-400" />
                </div>
                <div className="max-w-xs space-y-2">
                    <h3 className="text-lg font-semibold text-foreground">Verify Content</h3>
                    <p className="text-sm text-muted-foreground">
                        Analyze this video to identify factual claims and verify them against trusted sources.
                    </p>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors shadow-sm disabled:opacity-50"
                >
                    <ShieldCheck className="w-4 h-4" />
                    Verify Claims
                </button>
            </div>
        );
    }

    // Report view
    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
                <div className="flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                    <h3 className="font-semibold text-foreground">Verification Report</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        {report.claims.length} Claims
                    </span>
                </div>
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="p-2 hover:bg-muted rounded-full transition-colors disabled:opacity-50"
                    title="Re-analyze"
                >
                    <RefreshCw className="w-4 h-4 text-muted-foreground" />
                </button>
            </div>

            {/* Report Summary */}
            {report.summary && (
                <div className="px-4 py-3 bg-muted/20 border-b border-border">
                    <div className="flex gap-2">
                        <FileText className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                        <p className="text-sm text-muted-foreground leading-relaxed">{report.summary}</p>
                    </div>
                </div>
            )}

            {/* Claims List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {report.claims.map((claim) => (
                    <ClaimCard key={claim.claimId} claim={claim} onSeek={onSeek} />
                ))}

                <div className="text-center text-xs text-muted-foreground pt-4 pb-2">
                    Verified by Claude • {new Date(report.createdAt).toLocaleDateString()}
                </div>
            </div>
        </div>
    );
}
