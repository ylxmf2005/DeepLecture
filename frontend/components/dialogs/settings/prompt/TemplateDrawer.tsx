"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import {
    createPromptTemplate,
    getPromptTemplateText,
    updatePromptTemplate,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { toError } from "@/lib/utils/errorUtils";
import { logger } from "@/shared/infrastructure";
import { FUNC_ID_LABELS } from "./constants";
import type { DrawerState } from "./constants";
import type { PlaceholderMetadata } from "@/lib/api/types";

const log = logger.scope("TemplateDrawer");

function slugify(name: string): string {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "");
}

interface TemplateDrawerProps {
    state: DrawerState;
    metadata: Record<string, PlaceholderMetadata>;
    onClose: () => void;
    onSaved: () => void;
}

export function TemplateDrawer({ state, metadata, onClose, onSaved }: TemplateDrawerProps) {
    const { mode, funcId, sourceTemplate } = state;
    const funcMeta = metadata[funcId];
    const funcLabel = FUNC_ID_LABELS[funcId]?.label || funcId;

    const [name, setName] = useState("");
    const [implId, setImplId] = useState("");
    const [description, setDescription] = useState("");
    const [systemTemplate, setSystemTemplate] = useState("");
    const [userTemplate, setUserTemplate] = useState("");
    const [implIdManual, setImplIdManual] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const systemRef = useRef<HTMLTextAreaElement>(null);
    const userRef = useRef<HTMLTextAreaElement>(null);
    const lastFocusedRef = useRef<HTMLTextAreaElement | null>(null);
    const lastCursorRef = useRef<number>(0);

    // Load initial values based on mode
    useEffect(() => {
        setError(null);
        setImplIdManual(false);

        if (mode === "edit" && sourceTemplate) {
            setName(sourceTemplate.name);
            setImplId(sourceTemplate.implId);
            setDescription(sourceTemplate.description || "");
            setSystemTemplate(sourceTemplate.systemTemplate);
            setUserTemplate(sourceTemplate.userTemplate);
        } else if (mode === "duplicate" && sourceTemplate) {
            setName(`${sourceTemplate.name} (Copy)`);
            setImplId(`${sourceTemplate.implId}_copy`);
            setDescription(sourceTemplate.description || "");
            setSystemTemplate(sourceTemplate.systemTemplate);
            setUserTemplate(sourceTemplate.userTemplate);
        } else {
            // Create mode: fetch default template text for pre-filling
            setName("");
            setImplId("");
            setDescription("");
            setLoading(true);
            getPromptTemplateText(funcId, "default")
                .then((texts) => {
                    setSystemTemplate(texts.systemTemplate || "");
                    setUserTemplate(texts.userTemplate || "");
                })
                .catch(() => {
                    // Default builders may return empty strings — that's fine
                    setSystemTemplate("");
                    setUserTemplate("");
                })
                .finally(() => setLoading(false));
        }
    }, [mode, funcId, sourceTemplate]);

    const isDirty = useMemo(() => {
        if (mode === "edit" && sourceTemplate) {
            return (
                name !== sourceTemplate.name ||
                description !== (sourceTemplate.description || "") ||
                systemTemplate !== sourceTemplate.systemTemplate ||
                userTemplate !== sourceTemplate.userTemplate
            );
        }
        return name.trim() !== "" || systemTemplate.trim() !== "" || userTemplate.trim() !== "";
    }, [mode, sourceTemplate, name, description, systemTemplate, userTemplate]);

    const handleClose = useCallback(() => {
        if (isDirty) {
            if (!window.confirm("You have unsaved changes. Discard them?")) return;
        }
        onClose();
    }, [isDirty, onClose]);

    // Escape key handler
    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") handleClose();
        };
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, [handleClose]);

    const insertPlaceholder = useCallback(
        (placeholder: string) => {
            const textarea = lastFocusedRef.current;
            if (!textarea) {
                toast.info("Click a template field first");
                return;
            }
            const insertion = `{${placeholder}}`;
            const pos = lastCursorRef.current;
            const value = textarea === systemRef.current ? systemTemplate : userTemplate;
            const newValue = value.slice(0, pos) + insertion + value.slice(pos);

            if (textarea === systemRef.current) {
                setSystemTemplate(newValue);
            } else {
                setUserTemplate(newValue);
            }

            // Restore focus and cursor position after React re-render
            requestAnimationFrame(() => {
                textarea.focus();
                const newPos = pos + insertion.length;
                textarea.setSelectionRange(newPos, newPos);
                lastCursorRef.current = newPos;
            });
        },
        [systemTemplate, userTemplate],
    );

    const trackCursor = useCallback((textarea: HTMLTextAreaElement) => {
        lastFocusedRef.current = textarea;
        lastCursorRef.current = textarea.selectionStart;
    }, []);

    const handleSave = async () => {
        setError(null);
        setSaving(true);
        try {
            if (mode === "edit") {
                await updatePromptTemplate(funcId, implId, {
                    name: name.trim(),
                    description: description.trim() || undefined,
                    systemTemplate,
                    userTemplate,
                });
                toast.success("Template updated");
            } else {
                await createPromptTemplate({
                    funcId,
                    implId: implId.trim(),
                    name: name.trim(),
                    description: description.trim() || undefined,
                    systemTemplate,
                    userTemplate,
                });
                toast.success(mode === "duplicate" ? "Template duplicated" : "Template created");
            }
            onSaved();
        } catch (err) {
            const msg = toError(err).message;
            setError(msg);
            log.error("Failed to save template", toError(err));
        } finally {
            setSaving(false);
        }
    };

    const modeLabel = mode === "edit" ? "Edit Template" : mode === "duplicate" ? "Duplicate Template" : "New Template";

    return (
        <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="absolute inset-0 z-10 bg-white dark:bg-gray-800 flex flex-col overflow-hidden rounded-xl"
            role="dialog"
            aria-label={modeLabel}
        >
            {/* Header */}
            <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-100 dark:border-gray-700 shrink-0">
                <button
                    type="button"
                    onClick={handleClose}
                    className="p-1 rounded-md text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    aria-label="Close"
                >
                    <ArrowLeft className="w-4 h-4" />
                </button>
                <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                        {modeLabel}
                    </h3>
                    <p className="text-[11px] text-orange-600 dark:text-orange-400">{funcLabel}</p>
                </div>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {loading ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
                    </div>
                ) : (
                    <>
                        {/* Form fields */}
                        <div className="space-y-3">
                            <div className="space-y-1">
                                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                    Template Name
                                </label>
                                <input
                                    value={name}
                                    onChange={(e) => {
                                        const v = e.target.value;
                                        setName(v);
                                        if (!implIdManual) setImplId(slugify(v));
                                    }}
                                    placeholder="e.g. Concise Summary v2"
                                    className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-2.5">
                                <div className="space-y-1">
                                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                        Template ID
                                    </label>
                                    <input
                                        value={implId}
                                        onChange={(e) => {
                                            setImplIdManual(true);
                                            setImplId(e.target.value);
                                        }}
                                        disabled={mode === "edit"}
                                        placeholder="auto_generated"
                                        className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500 disabled:opacity-50"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                        Description <span className="text-gray-400 font-normal">(optional)</span>
                                    </label>
                                    <input
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                        placeholder="Brief description"
                                        className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Role explanation */}
                        <div className="rounded-md bg-orange-50 dark:bg-orange-900/20 border border-orange-100 dark:border-orange-800 px-3 py-2">
                            <p className="text-[11px] text-orange-800 dark:text-orange-300 leading-relaxed">
                                <strong>System Template</strong> sets the AI&apos;s role, persona, and behavioral
                                constraints. <strong>User Template</strong> defines the per-request prompt with
                                dynamic context.
                            </p>
                        </div>

                        {/* System Template */}
                        <div className="space-y-1">
                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                System Template
                            </label>
                            <textarea
                                ref={systemRef}
                                rows={6}
                                value={systemTemplate}
                                onChange={(e) => setSystemTemplate(e.target.value)}
                                onFocus={(e) => trackCursor(e.target)}
                                onSelect={(e) => {
                                    lastCursorRef.current = (e.target as HTMLTextAreaElement).selectionStart;
                                }}
                                placeholder="System instructions for the AI. Use {placeholder} for variables."
                                className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono text-gray-900 dark:text-gray-100 placeholder:text-gray-400 resize-y min-h-[80px] focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                aria-label="System template"
                            />
                        </div>

                        {/* User Template */}
                        <div className="space-y-1">
                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                                User Template
                            </label>
                            <textarea
                                ref={userRef}
                                rows={6}
                                value={userTemplate}
                                onChange={(e) => setUserTemplate(e.target.value)}
                                onFocus={(e) => trackCursor(e.target)}
                                onSelect={(e) => {
                                    lastCursorRef.current = (e.target as HTMLTextAreaElement).selectionStart;
                                }}
                                placeholder="User message template. Use {placeholder} for variables."
                                className="w-full rounded-md border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono text-gray-900 dark:text-gray-100 placeholder:text-gray-400 resize-y min-h-[80px] focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                                aria-label="User template"
                            />
                        </div>

                        {/* Placeholder Panel */}
                        {funcMeta && (
                            <div className="space-y-2">
                                <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400">
                                    Available Placeholders
                                    <span className="ml-1 text-gray-400">(click to insert)</span>
                                </span>
                                <div className="flex flex-wrap gap-1.5">
                                    {funcMeta.allowed.map((v) => {
                                        const isRequired = funcMeta.required.includes(v);
                                        const desc = funcMeta.descriptions[v];
                                        return (
                                            <button
                                                key={v}
                                                type="button"
                                                onClick={() => insertPlaceholder(v)}
                                                title={desc || v}
                                                role="button"
                                                aria-label={`Insert {${v}} placeholder`}
                                                className={cn(
                                                    "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-mono cursor-pointer transition-colors",
                                                    isRequired
                                                        ? "bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 hover:bg-orange-200 dark:hover:bg-orange-900/50"
                                                        : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600",
                                                )}
                                            >
                                                {`{${v}}`}
                                                {isRequired && <span className="text-orange-500">*</span>}
                                            </button>
                                        );
                                    })}
                                </div>
                                <p className="text-[10px] text-gray-400 dark:text-gray-500">
                                    <span className="text-orange-500">*</span> = required
                                    {funcMeta.allowed.some((v) => funcMeta.descriptions[v]) && (
                                        <span> &middot; hover for description</span>
                                    )}
                                </p>
                            </div>
                        )}

                        {/* Error */}
                        {error && (
                            <div className="rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2">
                                <p className="text-xs text-red-700 dark:text-red-400">{error}</p>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-100 dark:border-gray-700 shrink-0">
                <button
                    type="button"
                    onClick={handleClose}
                    className="rounded-md border border-gray-200 dark:border-gray-600 px-3 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                    Cancel
                </button>
                <button
                    type="button"
                    disabled={saving || loading}
                    onClick={handleSave}
                    className="inline-flex items-center gap-1.5 rounded-md bg-orange-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-700 disabled:opacity-60 transition-colors"
                >
                    {saving ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                        <Save className="w-3 h-3" />
                    )}
                    {saving ? "Saving..." : "Save"}
                </button>
            </div>
        </motion.div>
    );
}
