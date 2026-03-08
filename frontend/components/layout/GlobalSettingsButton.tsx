"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { Settings } from "lucide-react";
import { usePathname } from "next/navigation";

const SettingsDialog = dynamic(
    () => import("@/components/dialogs/SettingsDialog").then((mod) => mod.SettingsDialog),
    { ssr: false }
);

export function GlobalSettingsButton() {
    const pathname = usePathname();
    const [isOpen, setIsOpen] = useState(false);

    // Video page already injects a dedicated settings button into header actions.
    if (pathname?.startsWith("/video/")) return null;

    return (
        <>
            <button
                type="button"
                onClick={() => setIsOpen(true)}
                className="relative h-9 w-9 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                aria-label="Open global settings"
                title="Global Settings"
            >
                <Settings className="h-5 w-5" />
            </button>

            <SettingsDialog
                isOpen={isOpen}
                onClose={() => setIsOpen(false)}
                initialScope="global"
            />
        </>
    );
}
