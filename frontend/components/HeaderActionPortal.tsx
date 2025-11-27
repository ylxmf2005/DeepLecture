"use client";

import { createPortal } from "react-dom";

export function HeaderActionPortal({ children }: { children: React.ReactNode }) {
    // Guard against running during SSR where `document` is not defined.
    if (typeof document === "undefined") return null;

    const target = document.getElementById("header-actions");
    if (!target) return null;

    return createPortal(children, target);
}
