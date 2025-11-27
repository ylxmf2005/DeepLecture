/**
 * Subtitle search helpers.
 *
 * Use binary search instead of linear scan to drop O(n) to O(log n).
 * For 1,000 subtitles that means ~10 comparisons instead of 1,000.
 */

import { Subtitle } from "./srt";

/**
 * Binary search the subtitle index for the given timestamp.
 *
 * @param subtitles - Subtitles sorted by startTime
 * @param currentTime - Current playback time (seconds)
 * @returns Matching subtitle index, or -1 if none
 */
export function binarySearchSubtitle(
  subtitles: Subtitle[],
  currentTime: number
): number {
  if (!subtitles || subtitles.length === 0) return -1;

  let left = 0;
  let right = subtitles.length - 1;

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const sub = subtitles[mid];

    // Check whether the time falls within this subtitle
    if (currentTime >= sub.startTime && currentTime < sub.endTime) {
      return mid;
    }

    // If current time is before the subtitle start, search left half
    if (currentTime < sub.startTime) {
      right = mid - 1;
    } else {
      // Otherwise search right half
      left = mid + 1;
    }
  }

  return -1;
}

/**
 * Get active subtitles at the given time (supports overlapping cues).
 *
 * First binary-search for the primary hit, then scan nearby cues to
 * handle overlaps (lyrics, multi-language, etc.).
 *
 * @param subtitles - Subtitles sorted by startTime
 * @param currentTime - Current playback time (seconds)
 * @returns Array of active subtitles
 */
export function getActiveSubtitles(
  subtitles: Subtitle[],
  currentTime: number
): Subtitle[] {
  if (!subtitles || subtitles.length === 0) return [];

  const idx = binarySearchSubtitle(subtitles, currentTime);

  // No direct match found
  if (idx === -1) {
    // Extra check: binary search may land in a gap while overlaps exist
    // Scan the last few possible matches linearly
    const result: Subtitle[] = [];
    for (let i = Math.max(0, subtitles.length - 5); i < subtitles.length; i++) {
      if (
        currentTime >= subtitles[i].startTime &&
        currentTime < subtitles[i].endTime
      ) {
        result.push(subtitles[i]);
      }
    }
    return result;
  }

  const result: Subtitle[] = [subtitles[idx]];

  // Scan backward to include overlapping neighbors
  for (let i = idx - 1; i >= 0 && i >= idx - 3; i--) {
    if (
      currentTime >= subtitles[i].startTime &&
      currentTime < subtitles[i].endTime
    ) {
      result.unshift(subtitles[i]);
    } else if (subtitles[i].endTime <= subtitles[idx].startTime) {
      // Already fully before the active cue; stop scanning backward
      break;
    }
  }

  // Scan forward to include overlapping neighbors
  for (let i = idx + 1; i < subtitles.length && i <= idx + 3; i++) {
    if (
      currentTime >= subtitles[i].startTime &&
      currentTime < subtitles[i].endTime
    ) {
      result.push(subtitles[i]);
    } else if (subtitles[i].startTime >= currentTime) {
      // Later subtitles haven't started; stop scanning forward
      break;
    }
  }

  return result;
}

/**
 * Find the index of the subtitle closest to a target time.
 *
 * Useful for jumping to the nearest cue.
 *
 * @param subtitles - Subtitles sorted by startTime
 * @param targetTime - Target time (seconds)
 * @returns Nearest subtitle index, or -1 if list is empty
 */
export function findNearestSubtitle(
  subtitles: Subtitle[],
  targetTime: number
): number {
  if (!subtitles || subtitles.length === 0) return -1;

  let left = 0;
  let right = subtitles.length - 1;

  // Boundary cases
  if (targetTime <= subtitles[0].startTime) return 0;
  if (targetTime >= subtitles[right].startTime) return right;

  // Binary search for the nearest side
  while (left < right - 1) {
    const mid = Math.floor((left + right) / 2);
    if (subtitles[mid].startTime <= targetTime) {
      left = mid;
    } else {
      right = mid;
    }
  }

  // Compare which side is closer
  const leftDist = Math.abs(subtitles[left].startTime - targetTime);
  const rightDist = Math.abs(subtitles[right].startTime - targetTime);

  return leftDist <= rightDist ? left : right;
}

/**
 * Find the subtitle that should be active at a given time using "gap-filling" approach.
 *
 * Unlike binarySearchSubtitle which uses strict start/end bounds, this function
 * keeps a subtitle active until the next one starts. This is useful for repeat
 * functionality and continuous playback scenarios.
 *
 * @param time - Current playback time (seconds)
 * @param subtitles - Subtitles sorted by startTime
 * @returns The active subtitle, or null if none
 */
export function findSubtitleAtTime(
  time: number,
  subtitles: Subtitle[]
): Subtitle | null {
  if (!subtitles || subtitles.length === 0) {
    return null;
  }

  for (let i = 0; i < subtitles.length; i++) {
    const sub = subtitles[i];
    const nextStart =
      i + 1 < subtitles.length ? subtitles[i + 1].startTime : Number.POSITIVE_INFINITY;
    if (time >= sub.startTime && time < nextStart) {
      return sub;
    }
  }

  return null;
}
