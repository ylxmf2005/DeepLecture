"use client";

import { useRef, useEffect } from "react";
import { Worker, Viewer, SpecialZoomLevel } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import { cn } from "@/lib/utils";

const PDF_WORKER_URL = "https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js";

interface PdfSlideViewerProps {
    fileUrl: string;
}

export default function PdfSlideViewer({ fileUrl }: PdfSlideViewerProps) {
    "use no memo";

    const containerRef = useRef<HTMLDivElement>(null);

    // defaultLayoutPlugin() internally calls React.useMemo, making it
    // effectively a custom hook that MUST be called unconditionally.
    // We call it every render to maintain hook order, but only keep the
    // first result so the plugin instance is stable across renders.
    const freshPlugin = defaultLayoutPlugin({
        sidebarTabs: () => [],
        toolbarPlugin: {
            fullScreenPlugin: {
                enableShortcuts: false,
            },
        },
    });
    const layoutPluginRef = useRef(freshPlugin);
    const layoutPlugin = layoutPluginRef.current;

    // Re-zoom to PageWidth when the container width changes
    // (e.g. entering / exiting web-fullscreen or widescreen mode).
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;

        let prevWidth = el.clientWidth;

        const ro = new ResizeObserver((entries) => {
            const newWidth = entries[0]?.contentRect.width ?? 0;
            if (newWidth > 0 && newWidth !== prevWidth) {
                prevWidth = newWidth;
                layoutPlugin.toolbarPluginInstance.zoomPluginInstance.zoomTo(
                    SpecialZoomLevel.PageWidth
                );
            }
        });

        ro.observe(el);
        return () => ro.disconnect();
    }, [layoutPlugin]);

    return (
        <div
            ref={containerRef}
            className={cn(
                "w-full h-full bg-[#111827]",
                "[&_.rpv-core__inner-page]:min-h-full",
                "[&_.rpv-core__viewer]:h-full",
                "[&_[data-testid='full-screen__enter-button']]:hidden",
                "[&_[data-testid='full-screen__enter-menu']]:hidden",
                "[&_.rpv-full-screen__exit-button]:hidden"
            )}
        >
            <Worker workerUrl={PDF_WORKER_URL}>
                <Viewer
                    key={fileUrl}
                    fileUrl={fileUrl}
                    defaultScale={SpecialZoomLevel.PageWidth}
                    plugins={[layoutPlugin]}
                />
            </Worker>
        </div>
    );
}
