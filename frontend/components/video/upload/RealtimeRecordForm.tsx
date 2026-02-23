"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Mic, Pause, Play, Square } from "lucide-react";
import { useUploadQueueStore } from "@/stores/uploadQueueStore";
import {
    buildRecordingFilename,
    extensionFromMimeType,
    formatRecordingDuration,
    selectRecordingFormat,
} from "@/lib/mediaRecorder";
import { getErrorMessage, toError } from "@/lib/utils/errorUtils";
import { logger } from "@/shared/infrastructure";

type RecordingState = "idle" | "recording" | "paused" | "uploading";

interface RealtimeRecordFormProps {
    onSuccess: () => void;
}

const log = logger.scope("RealtimeRecordForm");

export function RealtimeRecordForm({ onSuccess }: RealtimeRecordFormProps) {
    const [customName, setCustomName] = useState("");
    const [state, setState] = useState<RecordingState>("idle");
    const [elapsedMs, setElapsedMs] = useState(0);

    const uploadRecordedAudio = useUploadQueueStore((s) => s.uploadRecordedAudio);
    const uploadingRecording = useUploadQueueStore((s) => s.uploadingRecording);
    const setError = useUploadQueueStore((s) => s.setError);
    const clearError = useUploadQueueStore((s) => s.clearError);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const chunksRef = useRef<BlobPart[]>([]);
    const shouldUploadRef = useRef(false);
    const elapsedBeforePauseMsRef = useRef(0);
    const startedAtMsRef = useRef<number | null>(null);
    const fallbackExtensionRef = useRef<"webm" | "mp4">("webm");

    const isBusy = useMemo(() => state === "uploading" || uploadingRecording, [state, uploadingRecording]);

    const stopTimer = useCallback(() => {
        if (timerRef.current !== null) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }
    }, []);

    const startTimer = useCallback(() => {
        stopTimer();
        timerRef.current = setInterval(() => {
            const runningMs = startedAtMsRef.current === null ? 0 : Date.now() - startedAtMsRef.current;
            setElapsedMs(elapsedBeforePauseMsRef.current + runningMs);
        }, 200);
    }, [stopTimer]);

    const stopStreamTracks = useCallback(() => {
        if (!streamRef.current) return;
        for (const track of streamRef.current.getTracks()) {
            track.stop();
        }
        streamRef.current = null;
    }, []);

    const resetElapsed = useCallback(() => {
        stopTimer();
        setElapsedMs(0);
        elapsedBeforePauseMsRef.current = 0;
        startedAtMsRef.current = null;
    }, [stopTimer]);

    const handleRecorderStop = useCallback(async () => {
        const recorder = mediaRecorderRef.current;
        mediaRecorderRef.current = null;
        stopTimer();
        stopStreamTracks();

        const shouldUpload = shouldUploadRef.current;
        shouldUploadRef.current = false;

        if (!shouldUpload) {
            resetElapsed();
            setState("idle");
            chunksRef.current = [];
            return;
        }

        try {
            setState("uploading");
            const mimeType = recorder?.mimeType || "";
            const extension = extensionFromMimeType(mimeType, fallbackExtensionRef.current);
            const blob = new Blob(chunksRef.current, { type: mimeType || `audio/${extension}` });
            chunksRef.current = [];

            const file = new File(
                [blob],
                buildRecordingFilename(customName, extension),
                { type: blob.type || `audio/${extension}` }
            );

            await uploadRecordedAudio(file, customName, () => {
                onSuccess();
            });
        } finally {
            resetElapsed();
            setState("idle");
        }
    }, [customName, onSuccess, resetElapsed, stopStreamTracks, stopTimer, uploadRecordedAudio]);

    const startRecording = useCallback(async () => {
        if (isBusy) return;

        clearError();
        shouldUploadRef.current = false;
        chunksRef.current = [];

        if (!navigator.mediaDevices?.getUserMedia) {
            setError("Recording is not supported in this browser.");
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;

            const format = selectRecordingFormat();
            fallbackExtensionRef.current = format.extension;

            let recorder: MediaRecorder;
            if (format.mimeType) {
                recorder = new MediaRecorder(stream, { mimeType: format.mimeType });
            } else {
                recorder = new MediaRecorder(stream);
            }

            recorder.ondataavailable = (event: BlobEvent) => {
                if (event.data.size > 0) {
                    chunksRef.current.push(event.data);
                }
            };

            recorder.onerror = (event: Event) => {
                log.error("MediaRecorder error", toError(event));
                setError("Recording failed. Please retry.");
                shouldUploadRef.current = false;
                stopTimer();
                stopStreamTracks();
                setState("idle");
            };

            recorder.onstop = () => {
                void handleRecorderStop();
            };

            recorder.start(250);
            mediaRecorderRef.current = recorder;
            elapsedBeforePauseMsRef.current = 0;
            startedAtMsRef.current = Date.now();
            setElapsedMs(0);
            setState("recording");
            startTimer();
        } catch (err) {
            log.error("Failed to start recording", toError(err));
            setError(getErrorMessage(err, "Unable to access microphone. Please allow microphone permissions."));
            shouldUploadRef.current = false;
            stopStreamTracks();
            setState("idle");
        }
    }, [clearError, handleRecorderStop, isBusy, setError, startTimer, stopStreamTracks, stopTimer]);

    const pauseRecording = useCallback(() => {
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state !== "recording") return;

        if (startedAtMsRef.current !== null) {
            elapsedBeforePauseMsRef.current += Date.now() - startedAtMsRef.current;
            startedAtMsRef.current = null;
        }
        setElapsedMs(elapsedBeforePauseMsRef.current);
        recorder.pause();
        stopTimer();
        setState("paused");
    }, [stopTimer]);

    const resumeRecording = useCallback(() => {
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state !== "paused") return;

        recorder.resume();
        startedAtMsRef.current = Date.now();
        setState("recording");
        startTimer();
    }, [startTimer]);

    const endAndUpload = useCallback(() => {
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state === "inactive") return;

        if (startedAtMsRef.current !== null) {
            elapsedBeforePauseMsRef.current += Date.now() - startedAtMsRef.current;
            startedAtMsRef.current = null;
        }

        shouldUploadRef.current = true;
        setElapsedMs(elapsedBeforePauseMsRef.current);
        setState("uploading");
        stopTimer();
        recorder.stop();
    }, [stopTimer]);

    useEffect(() => {
        return () => {
            stopTimer();
            shouldUploadRef.current = false;
            const recorder = mediaRecorderRef.current;
            if (recorder && recorder.state !== "inactive") {
                recorder.onstop = null;
                recorder.stop();
            }
            mediaRecorderRef.current = null;
            stopStreamTracks();
        };
    }, [stopStreamTracks, stopTimer]);

    return (
        <div className="space-y-4">
            <div className="p-4 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 space-y-4">
                <div>
                    <label htmlFor="recording-custom-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Recording Name (optional)
                    </label>
                    <input
                        id="recording-custom-name"
                        type="text"
                        value={customName}
                        onChange={(event) => setCustomName(event.target.value)}
                        placeholder="My Lecture Recording"
                        disabled={state !== "idle" || isBusy}
                        className="w-full px-3 py-2 border border-indigo-300 dark:border-indigo-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50"
                    />
                </div>

                <div className="rounded-lg bg-white/80 dark:bg-gray-900/30 border border-indigo-100 dark:border-indigo-900 p-3">
                    <p className="text-xs text-indigo-700 dark:text-indigo-300 mb-1">Status</p>
                    <p className="text-sm font-semibold text-indigo-800 dark:text-indigo-200 capitalize">{state}</p>
                    <p className="text-xs text-indigo-700/80 dark:text-indigo-300/80 mt-2">Duration: {formatRecordingDuration(elapsedMs)}</p>
                </div>

                <div className="flex flex-wrap gap-2">
                    {state === "idle" && (
                        <button
                            type="button"
                            onClick={() => void startRecording()}
                            disabled={isBusy}
                            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            <Mic className="w-4 h-4" />
                            Start Recording
                        </button>
                    )}

                    {state === "recording" && (
                        <>
                            <button
                                type="button"
                                onClick={pauseRecording}
                                disabled={isBusy}
                                className="px-4 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                <Pause className="w-4 h-4" />
                                Pause
                            </button>
                            <button
                                type="button"
                                onClick={endAndUpload}
                                disabled={isBusy}
                                className="px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                <Square className="w-4 h-4" />
                                End & Upload
                            </button>
                        </>
                    )}

                    {state === "paused" && (
                        <>
                            <button
                                type="button"
                                onClick={resumeRecording}
                                disabled={isBusy}
                                className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                <Play className="w-4 h-4" />
                                Resume
                            </button>
                            <button
                                type="button"
                                onClick={endAndUpload}
                                disabled={isBusy}
                                className="px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                <Square className="w-4 h-4" />
                                End & Upload
                            </button>
                        </>
                    )}

                    {state === "uploading" && (
                        <button
                            type="button"
                            disabled
                            className="px-4 py-2 text-sm font-medium text-white bg-indigo-500 rounded-lg cursor-not-allowed flex items-center gap-2"
                        >
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Uploading...
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
