"use client";

import { useEffect, useState, useCallback } from "react";
import {
    FolderOpen,
    Plus,
    Inbox,
    LayoutGrid,
    MoreHorizontal,
} from "lucide-react";
import { listProjects } from "@/lib/api";
import type { Project } from "@/lib/api/types";
import { CreateProjectDialog } from "./CreateProjectDialog";
import { EditProjectDialog } from "./EditProjectDialog";
import { cn } from "@/lib/utils";

interface ProjectFilterProps {
    selectedProjectId: string | null;
    onSelectProject: (projectId: string | null) => void;
    refreshTrigger?: number;
}

export function ProjectFilter({
    selectedProjectId,
    onSelectProject,
    refreshTrigger = 0,
}: ProjectFilterProps) {
    const [projects, setProjects] = useState<Project[]>([]);
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [editingProject, setEditingProject] = useState<Project | null>(null);

    const fetchProjects = useCallback(async () => {
        try {
            const data = await listProjects();
            setProjects(data.projects);
        } catch {
            // Silently fail — filter is non-critical
        }
    }, []);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects, refreshTrigger]);

    const handleProjectCreated = () => {
        setShowCreateDialog(false);
        fetchProjects();
    };

    const handleProjectUpdated = () => {
        setEditingProject(null);
        fetchProjects();
    };

    const isActive = (id: string | null) => selectedProjectId === id;

    const pillClass = (active: boolean) =>
        cn(
            "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors whitespace-nowrap cursor-pointer border",
            active
                ? "bg-primary/10 text-primary border-primary/20"
                : "bg-card text-muted-foreground border-border hover:bg-muted hover:text-foreground"
        );

    const projectPillClass = (active: boolean) =>
        cn(
            "relative inline-flex max-w-full shrink-0 items-center rounded-full border py-1.5 pl-3 pr-1 text-sm font-medium transition-colors",
            active
                ? "bg-primary/10 text-primary border-primary/20"
                : "bg-card text-muted-foreground border-border hover:bg-muted hover:text-foreground"
        );

    return (
        <>
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
                {/* All */}
                <button
                    className={pillClass(isActive(null))}
                    onClick={() => onSelectProject(null)}
                >
                    <LayoutGrid className="w-3.5 h-3.5" />
                    All
                </button>

                {/* Projects */}
                {projects.map((p) => (
                    <div key={p.id} className={cn("group/pill", projectPillClass(isActive(p.id)))}>
                        <button
                            type="button"
                            className="flex min-w-0 flex-1 items-center gap-1.5 pr-1"
                            onClick={() => onSelectProject(p.id)}
                        >
                            {p.color ? (
                                <span
                                    className="w-2.5 h-2.5 rounded-full shrink-0"
                                    style={{ backgroundColor: p.color }}
                                />
                            ) : (
                                <FolderOpen className="w-3.5 h-3.5" />
                            )}
                            <span className="truncate">
                                {p.icon ? `${p.icon} ` : ""}{p.name}
                            </span>
                            {p.contentCount > 0 && (
                                <span className="shrink-0 text-xs opacity-60">{p.contentCount}</span>
                            )}
                        </button>

                        {/* Context menu trigger */}
                        <button
                            type="button"
                            onClick={(e) => {
                                e.stopPropagation();
                                setEditingProject(p);
                            }}
                            className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-muted-foreground/80 transition-colors hover:bg-background/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                            aria-label={`Edit project ${p.name}`}
                            title={`Edit ${p.name}`}
                        >
                            <MoreHorizontal className="w-3.5 h-3.5" />
                        </button>
                    </div>
                ))}

                {/* Ungrouped */}
                <button
                    className={pillClass(isActive("none"))}
                    onClick={() => onSelectProject("none")}
                >
                    <Inbox className="w-3.5 h-3.5" />
                    Ungrouped
                </button>

                {/* Create project */}
                <button
                    onClick={() => setShowCreateDialog(true)}
                    className="inline-flex items-center justify-center w-8 h-8 rounded-full border border-dashed border-border text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors shrink-0"
                    title="New project"
                >
                    <Plus className="w-3.5 h-3.5" />
                </button>
            </div>

            {showCreateDialog && (
                <CreateProjectDialog
                    onClose={() => setShowCreateDialog(false)}
                    onCreated={handleProjectCreated}
                />
            )}

            {editingProject && (
                <EditProjectDialog
                    project={editingProject}
                    onClose={() => setEditingProject(null)}
                    onUpdated={handleProjectUpdated}
                />
            )}
        </>
    );
}
