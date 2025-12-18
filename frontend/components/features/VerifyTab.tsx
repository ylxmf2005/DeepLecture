"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { ShieldCheck, RefreshCw, AlertCircle, FileText, Loader2 } from "lucide-react";
import { ClaimCard } from "./ClaimCard";
import { getFactVerificationReport, generateFactVerification, isAPIError } from "@/lib/api";
import { useLanguageSettings } from "@/stores/useGlobalSettingsStore";
import { logger } from "@/shared/infrastructure";
import type { FactVerificationReport } from "@/lib/verifyTypes";

const log = logger.scope("VerifyTab");

interface VerifyTabProps {
    videoId: string;
    onSeek: (time: number) => void;
    refreshTrigger: number;
}

export function VerifyTab({ videoId, onSeek, refreshTrigger }: VerifyTabProps) {
    const { original: language } = useLanguageSettings();
    const [report, setReport] = useState<FactVerificationReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);

    // Track generating state across renders for SSE detection
    const isGeneratingRef = useRef(isGenerating);
    isGeneratingRef.current = isGenerating;

    // Track previous refreshTrigger to detect SSE notifications
    const prevRefreshTriggerRef = useRef(refreshTrigger);

    // Load report on mount and when refreshTrigger changes (consistent with ExplanationList pattern)
    // When refreshTrigger changes (SSE notification), it means task completed - we MUST reset isGenerating
    useEffect(() => {
        let cancelled = false;
        let retryCount = 0;
        const maxRetries = 3;
        const retryDelayMs = 1000;

        // Determine if this is an SSE-triggered reload (refreshTrigger changed while generating)
        const wasGenerating = isGeneratingRef.current;
        const triggerChanged = prevRefreshTriggerRef.current !== refreshTrigger;
        const isSSETriggered = triggerChanged && wasGenerating;
        prevRefreshTriggerRef.current = refreshTrigger;

        const loadReport = async () => {
            try {
                setLoading(true);
                log.debug("Loading verification report", { videoId, language, isSSETriggered, retryCount });
                const existing = await getFactVerificationReport(videoId, language);
                if (cancelled) return;
                if (existing) {
                    setReport(existing);
                    setLoadError(null);
                    // Report loaded successfully - if we were generating, task is now complete
                    setIsGenerating(false);
                    log.info("Verification report loaded", { videoId, language });
                } else if (isSSETriggered && retryCount < maxRetries) {
                    // SSE told us task completed but report not found yet - retry with delay
                    // This handles race condition where SSE arrives before file is readable
                    retryCount++;
                    log.debug("Report not found after SSE, retrying...", { videoId, language, retryCount });
                    setTimeout(() => {
                        if (!cancelled) loadReport();
                    }, retryDelayMs);
                    return; // Don't set loading=false yet
                } else if (isSSETriggered) {
                    // Retries exhausted - SSE said done but no report, likely error
                    log.warn("Report not found after retries, resetting state", { videoId, language });
                    setIsGenerating(false);
                    setLoadError("Verification completed but report not found. Please try again.");
                }
            } catch (err) {
                if (cancelled) return;
                if (isAPIError(err) && err.status === 404) {
                    log.debug("No existing verification report (404)", { videoId, language });
                    // If SSE triggered and got 404, retry or reset
                    if (isSSETriggered && retryCount < maxRetries) {
                        retryCount++;
                        log.debug("404 after SSE, retrying...", { videoId, language, retryCount });
                        setTimeout(() => {
                            if (!cancelled) loadReport();
                        }, retryDelayMs);
                        return;
                    } else if (isSSETriggered) {
                        // Retries exhausted
                        log.warn("404 after retries, resetting state", { videoId, language });
                        setIsGenerating(false);
                        setLoadError("Verification completed but report not found. Please try again.");
                    }
                } else {
                    log.error("Failed to load verification report", err instanceof Error ? err : undefined);
                    setLoadError("Failed to load report.");
                    setIsGenerating(false);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        if (videoId) {
            loadReport();
        }

        return () => {
            cancelled = true;
        };
    }, [videoId, language, refreshTrigger]);

    const handleGenerate = useCallback(async () => {
        setIsGenerating(true);
        setLoadError(null);

        try {
            await generateFactVerification({ contentId: videoId, language });
            // Task submitted, SSE will notify parent → parent bumps refreshTrigger → we re-fetch
            // Keep isGenerating=true until report loads successfully in useEffect
        } catch (err) {
            log.error("Failed to start verification", err instanceof Error ? err : undefined);
            setLoadError("Failed to start verification. Please try again.");
            setIsGenerating(false);
        }
    }, [videoId, language]);

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
                    onClick={() => setLoadError(null)}
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
