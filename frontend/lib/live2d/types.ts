/**
 * Type definitions for Live2D application-level interfaces.
 * These types define the public API surface for Live2D integration.
 */

export type LipSyncSource = 'none' | 'audio' | 'microphone' | 'manual';

export interface ModelMatrix {
    getArray(): number[];
    setMatrix(matrix: number[]): void;
}

export interface DeviceToScreen {
    transformX(x: number): number;
    transformY(y: number): number;
}

export interface LAppModelInfo {
    expressions: string[];
    motions: { group: string; count: number }[];
}

export interface LAppModel {
    _modelMatrix?: ModelMatrix;
    _modelSetting?: {
        _json?: {
            FileReferences?: {
                Expressions?: Array<{ Name?: string }>;
                Motions?: Record<string, unknown[]>;
            };
        };
    };
    getModel(): unknown;
    setDragging(x: number, y: number): void;
    hitTest(area: string, x: number, y: number): boolean;
    setExpression?(id: string): void;
    setRandomExpression?(): void;
    startMotion?(group: string, index: number, priority: number): void;
    startRandomMotion?(group: string, priority: number): void;
    anyhitTest?(x: number, y: number): string | null;
    isHitOnModel?(x: number, y: number): boolean;
    anyHitTestWithFallback?(x: number, y: number): boolean;
}

export interface LAppView {
    _deviceToScreen?: DeviceToScreen;
}

export interface LAppLive2DManager {
    getModel(index: number): unknown;
    loadModelByPath(dir: string, fileName: string): void;
    isMotionSyncModel?(modelName: string): boolean;
}

export interface LAppSubdelegateInterface {
    initialize(canvas: HTMLCanvasElement): boolean;
    release(): void;
    update(): void;
    getCanvas(): { width: number; height: number };
    getLive2DManager(): LAppLive2DManager;
    getView(): LAppView | null;
    getScale?(): number;

    // Pointer events
    onPointBeganLocal?(x: number, y: number): void;
    onPointMovedLocal?(x: number, y: number): void;
    onPointEndedLocal?(x: number, y: number): void;
    onWheel?(deltaY: number, localX: number, localY: number): void;

    // Expression and Motion
    setExpression?(expressionId: string): void;
    setRandomExpression?(): void;
    startMotion?(group: string, index: number, priority: number): void;
    startRandomMotion?(group: string, priority: number): void;
    getModelInfo?(): LAppModelInfo;

    // Lip Sync
    playAudioWithLipSync?(url: string): Promise<void>;
    connectAudioForLipSync?(audioElement: HTMLAudioElement): Promise<void>;
    startMicrophoneLipSync?(): Promise<void>;
    stopLipSync?(): Promise<void>;
    pauseLipSync?(): void;
    resumeLipSync?(): void;
    isLipSyncActive?(): boolean;
    getLipSyncSource?(): LipSyncSource;
    setLipSyncSmoothing?(value: number): void;
    setLipSyncGain?(value: number): void;
    setLipSyncValue?(value: number): void;
    getLipSyncValue?(): number;
    setOnLipSyncAudioEnded?(callback: (() => void) | null): void;
}

export interface Live2DCanvasHandle {
    setExpression: (expressionId: string) => void;
    setRandomExpression: () => void;
    startMotion: (group: string, index: number, priority?: number) => void;
    startRandomMotion: (group: string, priority?: number) => void;
    getModelInfo: () => LAppModelInfo | null;
    playAudioWithLipSync: (url: string) => Promise<void>;
    connectAudioForLipSync: (audioElement: HTMLAudioElement) => Promise<void>;
    startMicrophoneLipSync: () => Promise<void>;
    stopLipSync: () => Promise<void>;
    pauseLipSync: () => void;
    resumeLipSync: () => void;
    isLipSyncActive: () => boolean;
    getLipSyncSource: () => LipSyncSource;
    setLipSyncSmoothing: (value: number) => void;
    setLipSyncGain: (value: number) => void;
    setLipSyncValue: (value: number) => void;
    setOnLipSyncAudioEnded: (callback: (() => void) | null) => void;
    getLipSyncValue: () => number;
    getModelPosition: () => { x: number; y: number };
    setModelPosition: (x: number, y: number) => void;
    getModelScale: () => number;
    setModelScale: (scale: number) => void;
}

export interface Live2DViewerHandle {
    setExpression: (expressionId: string) => void;
    setRandomExpression: () => void;
    startMotion: (group: string, index: number, priority?: number) => void;
    startRandomMotion: (group: string, priority?: number) => void;
    getModelInfo: () => LAppModelInfo | null;
    playAudioWithLipSync: (url: string) => Promise<void>;
    connectAudioForLipSync: (audioElement: HTMLAudioElement) => Promise<void>;
    startMicrophoneLipSync: () => Promise<void>;
    stopLipSync: () => Promise<void>;
    pauseLipSync: () => void;
    resumeLipSync: () => void;
    isLipSyncActive: () => boolean;
    getLipSyncSource: () => LipSyncSource;
    setLipSyncSmoothing: (value: number) => void;
    setLipSyncGain: (value: number) => void;
    setLipSyncValue: (value: number) => void;
    setOnLipSyncAudioEnded: (callback: (() => void) | null) => void;
    getLipSyncValue: () => number;
}
