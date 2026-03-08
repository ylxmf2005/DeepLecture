"use client";

import { useEffect, useState, useCallback } from "react";
import {
    FolderOpen,
    Plus,
    ChevronLeft,
    ChevronRight,
    Inbox,
    LayoutGrid,
    MoreHorizontal,
    Edit2,
    Trash2,
    X,
} from "lucide-react";
import { listProjects, deleteProject } from "@/lib/api";
import type { Project } from "@/lib/api/types";
import { CreateProjectDialog } from "./CreateProjectDialog";
import { EditProjectDialog } from "./EditProjectDialog";
import { useConfirmDialog } from "@/contexts/ConfirmDialogContext";

interface ProjectSidebarProps {
    selectedProjectId: string | null;
    onSelectProject: (projectId: string | null) => void;
    refreshTrigger?: number;
}

const SIDEBAR_COLLAPSED_KEY = "courseSubtitle:sidebar-collapsed";

export function ProjectSidebar({
    selectedProjectId,
    onSelectProject,
    refreshTrigger = 0,
}: ProjectSidebarProps) {
    const [projects, setProjects] = useState<Project[]>([]);
    const [collapsed, setCollapsed] = useState(() => {
        if (typeof window === "undefined") return false;
        return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    });
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [editingProject, setEditingProject] = useState<Project | null>(null);
    const [contextMenuId, setContextMenuId] = useState<string | null>(null);
    const [mobileOpen, setMobileOpen] = useState(false);

    const { confirm } = useConfirmDialog();

    const fetchProjects = useCallback(async () => {
        try {
            const data = await listProjects();
            setProjects(data.projects);
        } catch {
            // Silently fail — sidebar is non-critical
        }
    }, []);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects, refreshTrigger]);

    const toggleCollapse = () => {
        const next = !collapsed;
        setCollapsed(next);
        if (typeof window !== "undefined") {
            window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
        }
    };

    const handleDeleteProject = async (projectId: string) => {
        setContextMenuId(null);
        const confirmed = await confirm({
            title: "Delete Project",
            message: "Delete this project? Content in it will become ungrouped.",
            confirmLabel: "Delete",
            cancelLabel: "Cancel",
            variant: "danger",
        });
        if (!confirmed) return;
        try {
            await deleteProject(projectId);
            if (selectedProjectId === projectId) {
                onSelectProject(null);
            }
            fetchProjects();
        } catch {
            // ignore
        }
    };

    const handleProjectCreated = () => {
        setShowCreateDialog(false);
        fetchProjects();
    };

    const handleProjectUpdated = () => {
        setEditingProject(null);
        fetchProjects();
    };

    const isActive = (id: string | null) => selectedProjectId === id;

    const itemClass = (active: boolean) =>
        `flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors ${
            active
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
        }`;

    const sidebarContent = (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-3 border-b border-border">
                <span className="font-semibold text-sm text-foreground">Projects</span>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => setShowCreateDialog(true)}
                        className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-muted transition-colors"
                        title="New project"
                    >
                        <Plus className="w-4 h-4" />
                    </button>
                    {/* Desktop collapse toggle */}
                    <button
                        onClick={toggleCollapse}
                        className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors hidden md:block"
                        title="Collapse sidebar"
                    >
                        <ChevronLeft className="w-4 h-4" />
                    </button>
                    {/* Mobile close */}
                    <button
                        onClick={() => setMobileOpen(false)}
                        className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors md:hidden"
                        title="Close"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 overflow-y-auto p-2 space-y-1">
                {/* All */}
                <div
                    className={itemClass(isActive(null))}
                    onClick={() => { onSelectProject(null); setMobileOpen(false); }}
                >
                    <LayoutGrid className="w-4 h-4 shrink-0" />
                    <span className="truncate">All</span>
                </div>

                {/* Projects */}
                {projects.map((p) => (
                    <div
                        key={p.id}
                        className={`${itemClass(isActive(p.id))} group/item relative`}
                        onClick={() => { onSelectProject(p.id); setMobileOpen(false); }}
                    >
                        {p.color ? (
                            <span
                                className="w-3 h-3 rounded-full shrink-0"
                                style={{ backgroundColor: p.color }}
                            />
                        ) : (
                            <FolderOpen className="w-4 h-4 shrink-0" />
                        )}
                        <span className="truncate flex-1">
                            {p.icon ? `${p.icon} ` : ""}{p.name}
                        </span>
                        <span className="text-xs text-muted-foreground shrink-0">
                            {p.contentCount}
                        </span>

                        {/* Context menu trigger */}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setContextMenuId(contextMenuId === p.id ? null : p.id);
                            }}
                            className="p-0.5 rounded opacity-0 group-hover/item:opacity-100 text-muted-foreground hover:text-foreground transition-opacity"
                        >
                            <MoreHorizontal className="w-3.5 h-3.5" />
                        </button>

                        {/* Dropdown menu */}
                        {contextMenuId === p.id && (
                            <div className="absolute right-0 top-full z-50 mt-1 w-36 bg-popover border border-border rounded-lg shadow-lg py-1">
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setContextMenuId(null);
                                        setEditingProject(p);
                                    }}
                                    className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-foreground hover:bg-muted"
                                >
                                    <Edit2 className="w-3.5 h-3.5" />
                                    Edit
                                </button>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteProject(p.id);
                                    }}
                                    className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-muted"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                    Delete
                                </button>
                            </div>
                        )}
                    </div>
                ))}

                {/* Ungrouped */}
                <div
                    className={itemClass(isActive("none"))}
                    onClick={() => { onSelectProject("none"); setMobileOpen(false); }}
                >
                    <Inbox className="w-4 h-4 shrink-0" />
                    <span className="truncate">Ungrouped</span>
                </div>
            </nav>
        </div>
    );

    // Close context menu when clicking outside
    useEffect(() => {
        if (!contextMenuId) return;
        const handler = () => setContextMenuId(null);
        document.addEventListener("click", handler);
        return () => document.removeEventListener("click", handler);
    }, [contextMenuId]);

    return (
        <>
            {/* Mobile toggle button */}
            <button
                onClick={() => setMobileOpen(true)}
                className="md:hidden fixed bottom-4 left-4 z-40 p-3 bg-primary text-primary-foreground rounded-full shadow-lg"
                title="Open projects"
            >
                <FolderOpen className="w-5 h-5" />
            </button>

            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    className="md:hidden fixed inset-0 z-40 bg-black/50"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Mobile slide-over */}
            <aside
                className={`md:hidden fixed inset-y-0 left-0 z-50 w-64 bg-card border-r border-border transform transition-transform ${
                    mobileOpen ? "translate-x-0" : "-translate-x-full"
                }`}
            >
                {sidebarContent}
            </aside>

            {/* Desktop sidebar */}
            {collapsed ? (
                <button
                    onClick={toggleCollapse}
                    className="hidden md:flex items-center justify-center w-10 h-10 mt-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
                    title="Expand sidebar"
                >
                    <ChevronRight className="w-4 h-4" />
                </button>
            ) : (
                <aside className="hidden md:block w-56 shrink-0 bg-card border border-border rounded-xl overflow-hidden h-fit sticky top-24">
                    {sidebarContent}
                </aside>
            )}

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
