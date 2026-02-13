export interface Subtitle {
    id: string;
    startTime: number;
    endTime: number;
    text: string;
}

function overlapSeconds(a: Subtitle, b: Subtitle): number {
    return Math.min(a.endTime, b.endTime) - Math.max(a.startTime, b.startTime);
}

function centerDistanceSeconds(a: Subtitle, b: Subtitle): number {
    const centerA = (a.startTime + a.endTime) / 2;
    const centerB = (b.startTime + b.endTime) / 2;
    return Math.abs(centerA - centerB);
}

function isTimingCompatible(a: Subtitle, b: Subtitle): boolean {
    return overlapSeconds(a, b) > 0 || Math.abs(a.startTime - b.startTime) <= 0.5;
}

/**
 * Find the best matching subtitle by time overlap first, then nearest center time.
 * Returns undefined when no reasonable timing match exists.
 */
export function findBestSubtitleByTime(
    source: Subtitle,
    candidates: Subtitle[],
    idLookup?: Map<string, Subtitle>
): Subtitle | undefined {
    const byId = idLookup?.get(source.id);
    if (byId && isTimingCompatible(source, byId)) {
        return byId;
    }

    let best: Subtitle | undefined;
    let bestOverlap = Number.NEGATIVE_INFINITY;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (const candidate of candidates) {
        const overlap = overlapSeconds(source, candidate);
        const distance = centerDistanceSeconds(source, candidate);

        if (overlap > bestOverlap) {
            best = candidate;
            bestOverlap = overlap;
            bestDistance = distance;
            continue;
        }

        if (overlap === bestOverlap && distance < bestDistance) {
            best = candidate;
            bestDistance = distance;
        }
    }

    if (!best) {
        return undefined;
    }

    // If no overlap exists at all, only accept near-by cues.
    if (bestOverlap <= 0 && bestDistance > 2.0) {
        return undefined;
    }

    return best;
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

export function mergeSubtitles(
    primary: Subtitle[],
    secondary: Subtitle[],
    primaryIsTop: boolean = true
): Subtitle[] {
    const secondaryById = new Map(secondary.map((sub) => [sub.id, sub]));

    return primary.map((sub) => {
        const secondarySub = findBestSubtitleByTime(sub, secondary, secondaryById);
        const secondaryText = secondarySub ? secondarySub.text : "";

        let text = "";
        if (primaryIsTop) {
            text = `${sub.text}\n${secondaryText}`;
        } else {
            text = `${secondaryText}\n${sub.text}`;
        }

        return {
            ...sub,
            text: text.trim(),
        };
    });
}
