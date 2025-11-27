"use client";

import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface MarkdownRendererProps {
    children: string;
    className?: string;
}

/**
 * Shared Markdown renderer with LaTeX support.
 *
 * Uses react-markdown + remark-math + rehype-katex so that all places
 * showing markdown (Ask, explanations, timeline, etc.) can render
 * `$inline$` and `$$block$$` math formulas.
 */
export function MarkdownRenderer({ children, className }: MarkdownRendererProps) {
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
            `}</style>
            <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
            >
                {children}
            </ReactMarkdown>
        </div>
    );
}
