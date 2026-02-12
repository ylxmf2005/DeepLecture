export interface SeekablePlayer {
    seekTo(time: number): void;
}

const DIRECT_SEEK_TOLERANCE_SECONDS = 0.05;

/**
 * Apply resume seek via player API when possible.
 * Always keeps direct video seek as a fallback so resume doesn't depend on
 * voiceover audio metadata timing.
 */
export function applyResumeSeek(
    targetTime: number,
    player: SeekablePlayer | null,
    video: HTMLVideoElement
): void {
    if (player) {
        try {
            player.seekTo(targetTime);
        } catch {
            // Fall through to direct video seek below.
        }
    }

    if (Math.abs(video.currentTime - targetTime) > DIRECT_SEEK_TOLERANCE_SECONDS) {
        video.currentTime = targetTime;
    }
}
