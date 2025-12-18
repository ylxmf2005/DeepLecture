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

export function mergeSubtitles(
    primary: Subtitle[],
    secondary: Subtitle[],
    primaryIsTop: boolean = true
): Subtitle[] {
    return primary.map((sub, index) => {
        const secondarySub = secondary[index];
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
