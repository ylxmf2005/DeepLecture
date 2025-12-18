"use client";

import { createContext, useContext } from "react";
import { useGlobalSettingsStore } from "@/stores";

/**
 * LearnerProfileProvider - Compatibility wrapper around useGlobalSettingsStore
 *
 * This provider maintains the same context API for backwards compatibility
 * but delegates to the zustand store for actual state management.
 * The learnerProfile is now automatically persisted via the store.
 */

type LearnerProfileContextValue = {
    profile: string;
    setProfile: (value: string) => void;
};

const LearnerProfileContext = createContext<LearnerProfileContextValue | undefined>(
    undefined
);

export function LearnerProfileProvider({ children }: { children: React.ReactNode }) {
    // Get state and action from store
    const profile = useGlobalSettingsStore((s) => s.learnerProfile);
    const setProfile = useGlobalSettingsStore((s) => s.setLearnerProfile);

    return (
        <LearnerProfileContext.Provider value={{ profile, setProfile }}>
            {children}
        </LearnerProfileContext.Provider>
    );
}

export function useLearnerProfile(): LearnerProfileContextValue {
    const ctx = useContext(LearnerProfileContext);
    if (!ctx) {
        throw new Error("useLearnerProfile must be used within a LearnerProfileProvider");
    }
    return ctx;
}
