"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, ShieldCheck, ShieldAlert, ShieldQuestion, AlertTriangle, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/timeFormat";
import type { Claim } from "@/lib/verifyTypes";

/** Only allow safe URL schemes to prevent XSS via javascript:/data: links */
function getSafeUrl(url: string): string | null {
    try {
        const parsed = new URL(url);
        if (parsed.protocol === "http:" || parsed.protocol === "https:") {
            return url;
        }
        return null;
    } catch {
        return null;
    }
}

interface ClaimCardProps {
    claim: Claim;
    onSeek: (time: number) => void;
}

export function ClaimCard({ claim, onSeek }: ClaimCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    const getVerdictStyle = (verdict: Claim["verdict"]) => {
        switch (verdict) {
            case "supported":
                return {
                    bg: "bg-green-100 dark:bg-green-900/30",
                    text: "text-green-700 dark:text-green-300",
                    border: "border-green-200 dark:border-green-800",
                    icon: ShieldCheck,
                    label: "Supported"
                };
            case "disputed":
                return {
                    bg: "bg-red-100 dark:bg-red-900/30",
                    text: "text-red-700 dark:text-red-300",
                    border: "border-red-200 dark:border-red-800",
                    icon: ShieldAlert,
                    label: "Disputed"
                };
            case "context_missing":
                return {
                    bg: "bg-orange-100 dark:bg-orange-900/30",
                    text: "text-orange-700 dark:text-orange-300",
                    border: "border-orange-200 dark:border-orange-800",
                    icon: AlertTriangle,
                    label: "Missing Context"
                };
            case "unverifiable":
            default:
                return {
                    bg: "bg-gray-100 dark:bg-gray-800",
                    text: "text-gray-700 dark:text-gray-300",
                    border: "border-gray-200 dark:border-gray-700",
                    icon: ShieldQuestion,
                    label: "Unverifiable"
                };
        }
    };

    const style = getVerdictStyle(claim.verdict);
    const Icon = style.icon;

    return (
        <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow">
            {/* Header / Main Content */}
            <div className="p-4">
                <div className="flex items-start justify-between gap-3 mb-2">
                    <div className={cn(
                        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
                        style.bg,
                        style.text,
                        style.border
                    )}>
                        <Icon className="w-3.5 h-3.5" />
                        {style.label}
                    </div>

                    <div className="flex items-center gap-2">
                         {/* Confidence Score */}
                         <div
                            className={cn(
                                "text-xs font-medium px-1.5 py-0.5 rounded",
                                claim.confidence >= 0.8
                                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                                    : claim.confidence >= 0.5
                                      ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300"
                                      : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                            )}
                            title="Confidence Score"
                         >
                            {Math.round(claim.confidence * 100)}%
                        </div>

                        {/* Timestamp Button */}
                        <button
                            onClick={() => onSeek(claim.start)}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 text-xs font-medium hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
                        >
                            <Play className="w-3 h-3 fill-current" />
                            {formatTime(claim.start)}
                        </button>
                    </div>
                </div>

                <p className="text-sm text-foreground font-medium leading-relaxed mb-3">
                    &quot;{claim.text}&quot;
                </p>

                {claim.notes && (
                    <p className="text-xs text-muted-foreground mb-3">
                        {claim.notes}
                    </p>
                )}

                {claim.evidence.length > 0 && (
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                        {isExpanded ? (
                            <>
                                <ChevronUp className="w-3.5 h-3.5" />
                                Hide Evidence ({claim.evidence.length})
                            </>
                        ) : (
                            <>
                                <ChevronDown className="w-3.5 h-3.5" />
                                Show Evidence ({claim.evidence.length})
                            </>
                        )}
                    </button>
                )}
            </div>

            {/* Evidence Section */}
            {isExpanded && claim.evidence.length > 0 && (
                <div className="border-t border-border bg-muted/30 px-4 py-3 space-y-3">
                    {claim.evidence.map((item, idx) => {
                        const safeUrl = getSafeUrl(item.url);
                        return (
                            <div key={idx} className="text-xs space-y-1">
                                <div className="flex items-center justify-between">
                                    <span className="font-medium text-foreground truncate max-w-[70%]">
                                        {item.publisher}
                                    </span>
                                    {safeUrl ? (
                                        <a
                                            href={safeUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline"
                                        >
                                            Source
                                            <ExternalLink className="w-3 h-3" />
                                        </a>
                                    ) : (
                                        <span className="text-muted-foreground">Source unavailable</span>
                                    )}
                                </div>
                                <p className="text-muted-foreground italic border-l-2 border-border pl-2 py-0.5 my-1">
                                    &quot;{item.quote}&quot;
                                </p>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
