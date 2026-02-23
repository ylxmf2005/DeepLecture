import { afterEach, describe, expect, it } from "vitest";
import {
    buildRecordingFilename,
    formatRecordingDuration,
    selectRecordingFormat,
} from "@/lib/mediaRecorder";

const ORIGINAL_MEDIA_RECORDER = globalThis.MediaRecorder;

function mockMediaRecorderSupport(supportedMimeTypes: string[]) {
    class MockMediaRecorder {}

    const recorderWithStatic = MockMediaRecorder as unknown as typeof MediaRecorder;
    recorderWithStatic.isTypeSupported = (mimeType: string) => supportedMimeTypes.includes(mimeType);

    Object.defineProperty(globalThis, "MediaRecorder", {
        configurable: true,
        writable: true,
        value: recorderWithStatic,
    });
}

afterEach(() => {
    Object.defineProperty(globalThis, "MediaRecorder", {
        configurable: true,
        writable: true,
        value: ORIGINAL_MEDIA_RECORDER,
    });
});

describe("selectRecordingFormat", () => {
    it("selects the highest-priority supported MIME type", () => {
        mockMediaRecorderSupport(["audio/webm", "audio/mp4"]);
        expect(selectRecordingFormat()).toEqual({
            mimeType: "audio/webm",
            extension: "webm",
        });
    });

    it("falls back to audio/mp4 when webm is not supported", () => {
        mockMediaRecorderSupport(["audio/mp4"]);
        expect(selectRecordingFormat()).toEqual({
            mimeType: "audio/mp4",
            extension: "mp4",
        });
    });

    it("returns safe fallback when no MIME types are supported", () => {
        mockMediaRecorderSupport([]);
        expect(selectRecordingFormat()).toEqual({
            mimeType: "",
            extension: "webm",
        });
    });

    it("returns safe fallback when MediaRecorder is unavailable", () => {
        Object.defineProperty(globalThis, "MediaRecorder", {
            configurable: true,
            writable: true,
            value: undefined,
        });
        expect(selectRecordingFormat()).toEqual({
            mimeType: "",
            extension: "webm",
        });
    });
});

describe("buildRecordingFilename", () => {
    it("uses custom name when provided", () => {
        expect(buildRecordingFilename("Lecture Intro", "webm")).toBe("Lecture Intro.webm");
    });

    it("strips audio extension from custom name", () => {
        expect(buildRecordingFilename("Lecture Intro.mp4", "webm")).toBe("Lecture Intro.webm");
    });

    it("uses timestamp fallback when custom name is empty", () => {
        const filename = buildRecordingFilename("", "webm", new Date("2026-02-23T12:34:56.000Z"));
        expect(filename).toBe("recording_20260223_123456.webm");
    });
});

describe("formatRecordingDuration", () => {
    it("formats duration as mm:ss under one hour", () => {
        expect(formatRecordingDuration(0)).toBe("00:00");
        expect(formatRecordingDuration(65_000)).toBe("01:05");
    });

    it("formats duration as hh:mm:ss when one hour or more", () => {
        expect(formatRecordingDuration(3_661_000)).toBe("01:01:01");
    });
});
