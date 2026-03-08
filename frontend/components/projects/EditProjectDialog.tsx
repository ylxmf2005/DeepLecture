"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { updateProject } from "@/lib/api";
import type { Project } from "@/lib/api/types";

const COLOR_PALETTE = [
    "#3B82F6", "#EF4444", "#10B981", "#F59E0B",
    "#8B5CF6", "#EC4899", "#06B6D4", "#F97316",
    "#14B8A6", "#6366F1", "#84CC16", "#A855F7",
];

interface EditProjectDialogProps {
    project: Project;
    onClose: () => void;
    onUpdated: () => void;
}

export function EditProjectDialog({ project, onClose, onUpdated }: EditProjectDialogProps) {
    const [name, setName] = useState(project.name);
    const [description, setDescription] = useState(project.description);
    const [color, setColor] = useState(project.color || COLOR_PALETTE[0]);
    const [icon, setIcon] = useState(project.icon);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const trimmed = name.trim();
        if (!trimmed) {
            setError("Name is required");
            return;
        }
        try {
            setSubmitting(true);
            setError(null);
            await updateProject(project.id, {
                name: trimmed,
                description: description.trim(),
                color,
                icon: icon.trim(),
            });
            onUpdated();
        } catch {
            setError("Failed to update project");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
            <div
                className="bg-card border border-border rounded-xl shadow-xl w-full max-w-md mx-4 p-6"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-foreground">Edit Project</h3>
                    <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground">
                        <X className="w-4 h-4" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-foreground mb-1">Name *</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            maxLength={100}
                            autoFocus
                            className="w-full px-3 py-2 border border-border rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-foreground mb-1">Description</label>
                        <input
                            type="text"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            maxLength={500}
                            className="w-full px-3 py-2 border border-border rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-foreground mb-1">Color</label>
                        <div className="flex flex-wrap gap-2">
                            {COLOR_PALETTE.map((c) => (
                                <button
                                    key={c}
                                    type="button"
                                    onClick={() => setColor(c)}
                                    className={`w-7 h-7 rounded-full transition-all ${
                                        color === c ? "ring-2 ring-offset-2 ring-primary" : ""
                                    }`}
                                    style={{ backgroundColor: c }}
                                />
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-foreground mb-1">Icon (emoji)</label>
                        <input
                            type="text"
                            value={icon}
                            onChange={(e) => setIcon(e.target.value)}
                            maxLength={4}
                            className="w-16 px-3 py-2 border border-border rounded-lg bg-background text-foreground text-center text-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
                            placeholder="📐"
                        />
                    </div>

                    {error && <p className="text-sm text-red-500">{error}</p>}

                    <div className="flex justify-end gap-2 pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-sm rounded-lg border border-border text-foreground hover:bg-muted"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={submitting || !name.trim()}
                            className="px-4 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                        >
                            {submitting ? "Saving..." : "Save"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
