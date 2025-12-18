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

    if (currentTime >= sub.startTime && currentTime < sub.endTime) {
      return mid;
    }

    if (currentTime < sub.startTime) {
      right = mid - 1;
    } else {
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

  if (idx === -1) {
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

  for (let i = idx - 1; i >= 0 && i >= idx - 3; i--) {
    if (
      currentTime >= subtitles[i].startTime &&
      currentTime < subtitles[i].endTime
    ) {
      result.unshift(subtitles[i]);
    } else if (subtitles[i].endTime <= subtitles[idx].startTime) {
      break;
    }
  }

  for (let i = idx + 1; i < subtitles.length && i <= idx + 3; i++) {
    if (
      currentTime >= subtitles[i].startTime &&
      currentTime < subtitles[i].endTime
    ) {
      result.push(subtitles[i]);
    } else if (subtitles[i].startTime >= currentTime) {
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

  if (targetTime <= subtitles[0].startTime) return 0;
  if (targetTime >= subtitles[right].startTime) return right;

  while (left < right - 1) {
    const mid = Math.floor((left + right) / 2);
    if (subtitles[mid].startTime <= targetTime) {
      left = mid;
    } else {
      right = mid;
    }
  }

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

  // Binary search for the last subtitle whose startTime <= time
  let left = 0;
  let right = subtitles.length - 1;

  if (time < subtitles[0].startTime) return null;

  while (left < right) {
    const mid = Math.floor((left + right + 1) / 2);
    if (subtitles[mid].startTime <= time) {
      left = mid;
    } else {
      right = mid - 1;
    }
  }

  const sub = subtitles[left];
  const nextStart =
    left + 1 < subtitles.length ? subtitles[left + 1].startTime : Number.POSITIVE_INFINITY;

  return time >= sub.startTime && time < nextStart ? sub : null;
}
