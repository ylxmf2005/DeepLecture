export interface Subtitle {
    id: string;
    startTime: number;
    endTime: number;
    text: string;
}

export function parseSRT(content: string): Subtitle[] {
    const subtitles: Subtitle[] = [];
    const blocks = content.trim().split(/\n\s*\n/);

    for (const block of blocks) {
        const lines = block.split("\n");
        if (lines.length < 3) continue;

        const id = lines[0].trim();
        const timeMatch = lines[1].match(
            /(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})/
        );

        if (!timeMatch) continue;

        const startTime =
            parseInt(timeMatch[1], 10) * 3600 +
            parseInt(timeMatch[2], 10) * 60 +
            parseInt(timeMatch[3], 10) +
            parseInt(timeMatch[4], 10) / 1000;

        const endTime =
            parseInt(timeMatch[5], 10) * 3600 +
            parseInt(timeMatch[6], 10) * 60 +
            parseInt(timeMatch[7], 10) +
            parseInt(timeMatch[8], 10) / 1000;

        const text = cleanSubtitleText(lines.slice(2).join("\n"));

        subtitles.push({
            id,
            startTime,
            endTime,
            text,
        });
    }

    return subtitles;
}

function cleanSubtitleText(text: string): string {
    return text
        .replace(/<[^>]+>/g, "")
        .replace(/\{.*?\}/g, "")
        .trim();
}

export function stringifySRT(subtitles: Subtitle[]): string {
    return subtitles
        .map((sub, index) => {
            const startTime = formatTimestamp(sub.startTime);
            const endTime = formatTimestamp(sub.endTime);
            return `${index + 1}\n${startTime} --> ${endTime}\n${sub.text}\n`;
        })
        .join("\n");
}

export function stringifyVTT(subtitles: Subtitle[]): string {
    const cues = subtitles
        .map((sub, index) => {
            const startTime = formatVttTimestamp(sub.startTime);
            const endTime = formatVttTimestamp(sub.endTime);
            return `${index + 1}\n${startTime} --> ${endTime} line:85%\n${sub.text}\n`;
        })
        .join("\n");

    return `WEBVTT\n\n${cues}`.trimEnd() + "\n";
}

function formatTimestamp(seconds: number): string {
    const date = new Date(0);
    date.setMilliseconds(seconds * 1000);
    const hours = date.getUTCHours().toString().padStart(2, "0");
    const minutes = date.getUTCMinutes().toString().padStart(2, "0");
    const secs = date.getUTCSeconds().toString().padStart(2, "0");
    const ms = date.getUTCMilliseconds().toString().padStart(3, "0");
    return `${hours}:${minutes}:${secs},${ms}`;
}

function formatVttTimestamp(seconds: number): string {
    const date = new Date(0);
    date.setMilliseconds(seconds * 1000);
    const hours = date.getUTCHours().toString().padStart(2, "0");
    const minutes = date.getUTCMinutes().toString().padStart(2, "0");
    const secs = date.getUTCSeconds().toString().padStart(2, "0");
    const ms = date.getUTCMilliseconds().toString().padStart(3, "0");
    return `${hours}:${minutes}:${secs}.${ms}`;
}

/**
 * Merge two subtitle tracks into bilingual subtitles by matching time intervals.
 *
 * Uses time-interval overlap matching instead of array index to handle cases where
 * LLM merges multiple short segments into fewer longer ones. For each primary
 * subtitle, finds the secondary subtitle with the maximum time overlap.
 *
 * Algorithm: Two-pointer scan after sorting by startTime, O(n + m) complexity.
 *
 * @param primary - Primary subtitle track (determines output timing)
 * @param secondary - Secondary subtitle track to merge
 * @param primaryIsTop - If true, primary text appears first; otherwise secondary first
 */
export function mergeSubtitles(
    primary: Subtitle[],
    secondary: Subtitle[],
    primaryIsTop: boolean = true
): Subtitle[] {
    if (secondary.length === 0) {
        return primary.map((sub) => ({ ...sub }));
    }

    // Sort both arrays by startTime (defensive copy to avoid mutation)
    const sortedSecondary = [...secondary].sort((a, b) => a.startTime - b.startTime);

    // Two-pointer approach: for each primary, find best overlapping secondary
    let secIdx = 0;

    return primary.map((sub) => {
        // Advance secIdx to first secondary that could possibly overlap
        // (secondary.endTime > primary.startTime)
        while (secIdx < sortedSecondary.length && sortedSecondary[secIdx].endTime <= sub.startTime) {
            secIdx++;
        }

        // Find the secondary with maximum overlap in the candidate window
        let bestMatch: Subtitle | undefined;
        let bestOverlap = 0;

        for (let i = secIdx; i < sortedSecondary.length; i++) {
            const sec = sortedSecondary[i];

            // Stop if secondary starts after primary ends (no more possible overlaps)
            if (sec.startTime >= sub.endTime) {
                break;
            }

            // Calculate overlap: max(0, min(end1, end2) - max(start1, start2))
            const overlapStart = Math.max(sub.startTime, sec.startTime);
            const overlapEnd = Math.min(sub.endTime, sec.endTime);
            const overlap = Math.max(0, overlapEnd - overlapStart);

            if (overlap > bestOverlap) {
                bestOverlap = overlap;
                bestMatch = sec;
            }
        }

        const secondaryText = bestMatch?.text ?? "";

        const text = primaryIsTop
            ? `${sub.text}\n${secondaryText}`
            : `${secondaryText}\n${sub.text}`;

        return {
            ...sub,
            text: text.trim(),
        };
    });
}
