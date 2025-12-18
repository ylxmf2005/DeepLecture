"use client";

import { memo, useMemo } from "react";
import { cn } from "@/lib/utils";
import { sanitizeUrl } from "@/lib/utils/security";
import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Clock } from "lucide-react";
import "katex/dist/katex.min.css";
import { remarkSeekableTimestamps } from "@/lib/markdown/remarkSeekableTimestamps";
import { parseSeekHrefSeconds } from "@/lib/markdown/timestamps";
import { useVideoPlayerOptional } from "@/contexts/VideoPlayerContext";

interface MarkdownRendererProps {
    children: string;
    className?: string;
    onSeek?: (seconds: number) => void;
}

/**
 * Custom components for ReactMarkdown with security hardening.
 * Validates URLs to prevent javascript: and other dangerous protocols.
 */
function makeSecureComponents(onSeek: ((seconds: number) => void) | undefined): Components {
    return {
        a: ({ href, children, className, ...props }) => {
            const safeHref = sanitizeUrl(href);
            if (!safeHref) {
                // Render as plain text if URL is unsafe
                return <span {...props}>{children}</span>;
            }

            const seekSeconds = parseSeekHrefSeconds(safeHref);
            if (seekSeconds !== null) {
                // Render as non-clickable span when no seek handler available
                if (!onSeek) {
                    return (
                        <span className={cn("seek-timestamp-inactive", className)} {...props}>
                            <span className="seek-timestamp-content">
                                <Clock className="seek-timestamp-icon" />
                                <span className="seek-timestamp-text">{children}</span>
                            </span>
                        </span>
                    );
                }
                return (
                    <a
                        href={safeHref}
                        data-seek="true"
                        className={cn("seek-timestamp-link", className)}
                        onClick={(e) => {
                            e.preventDefault();
                            onSeek(seekSeconds);
                        }}
                        {...props}
                    >
                        <span className="seek-timestamp-content">
                            <Clock className="seek-timestamp-icon" />
                            <span className="seek-timestamp-text">{children}</span>
                        </span>
                    </a>
                );
            }

            return (
                <a
                    href={safeHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    {...props}
                >
                    {children}
                </a>
            );
        },
    };
}

/**
 * Shared Markdown renderer with LaTeX support and XSS protection.
 *
 * Uses react-markdown + remark-math + rehype-katex so that all places
 * showing markdown (Ask, explanations, timeline, etc.) can render
 * `$inline$` and `$$block$$` math formulas.
 *
 * Security: Links are validated to prevent javascript: URLs.
 * External links open in new tabs with noopener noreferrer.
 */
function MarkdownRendererBase({ children, className, onSeek }: MarkdownRendererProps) {
    const player = useVideoPlayerOptional();
    const seek = onSeek ?? player?.seekTo;
    const components = useMemo(() => makeSecureComponents(seek), [seek]);
    return (
        <div className={cn("markdown-body text-sm leading-relaxed", className)}>
            <style jsx global>{`
                .markdown-body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                    font-size: 14px;
                    line-height: 1.7;
                    color: #111827;
                }
                .dark .markdown-body {
                    color: #e5e7eb;
                }
                .markdown-body h1,
                .markdown-body h2,
                .markdown-body h3 {
                    font-weight: 600;
                    margin: 0.75rem 0 0.5rem;
                }
                .markdown-body ul,
                .markdown-body ol {
                    padding-left: 1.25rem;
                    margin: 0.5rem 0;
                }
                .markdown-body p {
                    margin: 0.5rem 0;
                }
                .markdown-body code {
                    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                }
                .markdown-body pre {
                    padding: 0.75rem 1rem;
                    background-color: #f9fafb;
                    border-radius: 0.5rem;
                    overflow-x: auto;
                }
                .dark .markdown-body pre {
                    background-color: #111827;
                }
                .markdown-body table {
                    border-collapse: collapse;
                    margin: 0.75rem 0;
                    width: 100%;
                }
                .markdown-body table th,
                .markdown-body table td {
                    border: 1px solid #e5e7eb;
                    padding: 0.35rem 0.5rem;
                }
                .dark .markdown-body table th,
                .dark .markdown-body table td {
                    border-color: #374151;
                }
                .markdown-body .katex-display {
                    margin: 0.75rem 0;
                }

                .markdown-body a[data-seek="true"] {
                    color: #2563eb;
                    text-decoration: none;
                    border-radius: 0.375rem;
                    padding: 0.05rem 0.3rem;
                    background: rgba(37, 99, 235, 0.08);
                    border: 1px solid rgba(37, 99, 235, 0.18);
                    display: inline-flex;
                    align-items: center;
                }
                .dark .markdown-body a[data-seek="true"] {
                    color: #93c5fd;
                    background: rgba(147, 197, 253, 0.12);
                    border-color: rgba(147, 197, 253, 0.25);
                }
                .markdown-body a[data-seek="true"]:hover {
                    background: rgba(37, 99, 235, 0.14);
                }
                .dark .markdown-body a[data-seek="true"]:hover {
                    background: rgba(147, 197, 253, 0.18);
                }
                .markdown-body .seek-timestamp-content {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.25rem;
                }
                .markdown-body .seek-timestamp-icon {
                    width: 0.85rem;
                    height: 0.85rem;
                }
                .markdown-body .seek-timestamp-text {
                    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
                        "Courier New", monospace;
                    font-variant-numeric: tabular-nums;
                }
                .markdown-body .seek-timestamp-inactive {
                    color: #6b7280;
                    border-radius: 0.375rem;
                    padding: 0.05rem 0.3rem;
                    background: rgba(107, 114, 128, 0.08);
                    border: 1px solid rgba(107, 114, 128, 0.18);
                    display: inline-flex;
                    align-items: center;
                }
                .dark .markdown-body .seek-timestamp-inactive {
                    color: #9ca3af;
                    background: rgba(156, 163, 175, 0.12);
                    border-color: rgba(156, 163, 175, 0.25);
                }
            `}</style>
            <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath, remarkSeekableTimestamps]}
                rehypePlugins={[rehypeKatex]}
                components={components}
            >
                {children}
            </ReactMarkdown>
        </div>
    );
}

export const MarkdownRenderer = memo(MarkdownRendererBase);
