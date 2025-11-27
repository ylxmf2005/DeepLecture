import { useCallback, useRef } from "react";

const UI_UPDATE_INTERVAL_MS = 250; // 4fps for UI updates

interface UseThrottledTimeUpdateOptions {
    onTimeChange: (time: number) => void;
    onSmartSkipCheck?: (time: number) => boolean; // Returns true if skip was triggered
    onPersistProgress?: (time: number) => void;
}

/**
 * Hook that throttles UI time updates while keeping smart skip checks responsive.
 * - Smart skip checks run on every time update (for responsive skipping)
 * - UI updates (setCurrentTime) are throttled to 4fps
 * - Progress persistence uses its own threshold
 */
export function useThrottledTimeUpdate({
    onTimeChange,
    onSmartSkipCheck,
    onPersistProgress,
}: UseThrottledTimeUpdateOptions) {
    const lastUIUpdateRef = useRef(0);

    const handleTimeUpdate = useCallback(
        (time: number) => {
            // Smart skip check runs on every update for responsiveness
            if (onSmartSkipCheck) {
                const skipTriggered = onSmartSkipCheck(time);
                if (skipTriggered) {
                    return; // Skip was triggered, don't update UI yet
                }
            }

            // Throttle UI updates to reduce re-renders
            const now = Date.now();
            if (now - lastUIUpdateRef.current >= UI_UPDATE_INTERVAL_MS) {
                lastUIUpdateRef.current = now;
                onTimeChange(time);
            }

            // Progress persistence (has its own internal threshold)
            if (onPersistProgress) {
                onPersistProgress(time);
            }
        },
        [onTimeChange, onSmartSkipCheck, onPersistProgress]
    );

    return handleTimeUpdate;
}
