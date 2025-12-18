"use client";

import { useState, useCallback } from "react";
import {
    PointerSensor,
    useSensor,
    useSensors,
    closestCenter,
    pointerWithin,
    type DragEndEvent,
    type DragStartEvent,
    type DragOverEvent,
    type DragCancelEvent,
    type CollisionDetection,
} from "@dnd-kit/core";
import {
    useTabLayoutStore,
    findTabPanel,
    LAYOUT_CONSTRAINTS,
    type TabId,
    type PanelId,
} from "@/stores";

export interface UseDndTabLayoutReturn {
    activeId: TabId | null;
    sensors: ReturnType<typeof useSensors>;
    collisionDetection: CollisionDetection;
    handleDragStart: (event: DragStartEvent) => void;
    handleDragOver: (event: DragOverEvent) => void;
    handleDragEnd: (event: DragEndEvent) => void;
    handleDragCancel: (event: DragCancelEvent) => void;
}

/**
 * Hook to manage drag-and-drop for tab layout panels
 */
export function useDndTabLayout(): UseDndTabLayoutReturn {
    const [activeId, setActiveId] = useState<TabId | null>(null);

    const tabPanels = useTabLayoutStore((state) => state.panels);
    const moveTab = useTabLayoutStore((state) => state.moveTab);
    const reorderTab = useTabLayoutStore((state) => state.reorderTab);
    const startDrag = useTabLayoutStore((state) => state.startDrag);
    const commitDrag = useTabLayoutStore((state) => state.commitDrag);
    const rollbackDrag = useTabLayoutStore((state) => state.rollbackDrag);

    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8,
            },
        })
    );

    // Custom collision detection: prioritize pointerWithin, fallback to closestCenter
    const collisionDetection: CollisionDetection = useCallback((args) => {
        const pointerCollisions = pointerWithin(args);
        if (pointerCollisions.length > 0) {
            return pointerCollisions;
        }
        return closestCenter(args);
    }, []);

    const handleDragStart = useCallback((event: DragStartEvent) => {
        startDrag(); // Snapshot state for potential rollback
        setActiveId(event.active.id as TabId);
    }, [startDrag]);

    const handleDragOver = useCallback(
        (event: DragOverEvent) => {
            const { active, over } = event;
            if (!over) return;

            const activeTabId = active.id as TabId;
            const overId = over.id as string;

            const sourcePanel = findTabPanel(tabPanels, activeTabId);
            if (!sourcePanel) return;

            let targetPanel: PanelId;
            if (overId === "sidebar" || overId === "bottom") {
                targetPanel = overId as PanelId;
            } else {
                const overTabPanel = findTabPanel(tabPanels, overId as TabId);
                if (!overTabPanel) return;
                targetPanel = overTabPanel;
            }

            // Only handle cross-panel moves during drag over
            if (sourcePanel === targetPanel) return;

            // Check capacity constraint
            const maxTarget = targetPanel === "sidebar"
                ? LAYOUT_CONSTRAINTS.MAX_SIDEBAR_TABS
                : LAYOUT_CONSTRAINTS.MAX_BOTTOM_TABS;
            if (tabPanels[targetPanel].length >= maxTarget) return;

            // Calculate target index
            let targetIndex: number;
            if (overId === "sidebar" || overId === "bottom") {
                targetIndex = tabPanels[targetPanel].length;
            } else {
                const overIndex = tabPanels[targetPanel].indexOf(overId as TabId);
                const activeRect = active.rect.current.translated;
                const overRect = over.rect;

                if (activeRect && overRect) {
                    const activeCenterX = activeRect.left + activeRect.width / 2;
                    const overCenterX = overRect.left + overRect.width / 2;
                    targetIndex = activeCenterX > overCenterX ? overIndex + 1 : overIndex;
                } else {
                    targetIndex = overIndex;
                }
            }

            moveTab(activeTabId, sourcePanel, targetPanel, targetIndex);
        },
        [tabPanels, moveTab]
    );

    const handleDragEnd = useCallback(
        (event: DragEndEvent) => {
            const { active, over } = event;
            setActiveId(null);
            commitDrag(); // Clear snapshot on successful drop

            if (!over) return;

            const activeTabId = active.id as TabId;
            const overId = over.id as string;

            const sourcePanel = findTabPanel(tabPanels, activeTabId);
            if (!sourcePanel) return;

            // Skip if dropped on a panel directly - already handled by handleDragOver
            if (overId === "sidebar" || overId === "bottom") return;

            const overTabPanel = findTabPanel(tabPanels, overId as TabId);
            if (!overTabPanel) return;

            // Only handle same-panel reordering here
            if (sourcePanel !== overTabPanel) return;

            const overIndex = tabPanels[sourcePanel].indexOf(overId as TabId);
            const oldIndex = tabPanels[sourcePanel].indexOf(activeTabId);
            const isLastItem = overIndex === tabPanels[sourcePanel].length - 1;

            const activeRect = active.rect.current.translated;
            const overRect = over.rect;

            let targetIndex: number;
            if (activeRect && overRect) {
                const activeCenterX = activeRect.left + activeRect.width / 2;
                const overCenterX = overRect.left + overRect.width / 2;

                if (oldIndex < overIndex) {
                    targetIndex = overIndex;
                } else if (oldIndex > overIndex) {
                    targetIndex = overIndex;
                } else {
                    return; // Same position, no change
                }

                if (isLastItem && activeCenterX > overCenterX) {
                    targetIndex = tabPanels[sourcePanel].length;
                }
            } else {
                targetIndex = overIndex;
            }

            if (oldIndex !== targetIndex && oldIndex !== -1) {
                reorderTab(sourcePanel, oldIndex, targetIndex);
            }
        },
        [tabPanels, reorderTab, commitDrag]
    );

    const handleDragCancel = useCallback(
        () => {
            setActiveId(null);
            rollbackDrag(); // Restore state from snapshot
        },
        [rollbackDrag]
    );

    return {
        activeId,
        sensors,
        collisionDetection,
        handleDragStart,
        handleDragOver,
        handleDragEnd,
        handleDragCancel,
    };
}
