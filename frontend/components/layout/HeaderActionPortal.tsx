"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

export function HeaderActionPortal({ children }: { children: React.ReactNode }) {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    // Server-side and first client render both return null → no hydration mismatch
    if (!mounted) return null;

    const target = document.getElementById("header-actions");
    if (!target) return null;

    return createPortal(children, target);
}
