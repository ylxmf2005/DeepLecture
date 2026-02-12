export interface ResumeCandidateInput {
    resumeTarget: number | null;
    persistedProgress: number | null;
}

/**
 * Pick the best available resume candidate.
 * Priority:
 * 1) In-memory resume target (already initialized by hook)
 * 2) Persisted progress from store (hydration fallback)
 */
export function getResumeCandidate({
    resumeTarget,
    persistedProgress,
}: ResumeCandidateInput): number | null {
    if (typeof resumeTarget === "number" && Number.isFinite(resumeTarget) && resumeTarget > 0) {
        return resumeTarget;
    }

    if (typeof persistedProgress === "number" && Number.isFinite(persistedProgress) && persistedProgress > 0) {
        return persistedProgress;
    }

    return null;
}
