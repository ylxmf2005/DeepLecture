'use client';

/**
 * Live2D Canvas Component - Full-screen mode with model-level dragging and scaling
 *
 * Key features:
 * - Canvas covers entire container (or viewport)
 * - Drag the model itself (not a window)
 * - Scale the model with mouse wheel
 * - Click-through: only responds when clicking on the model
 */

import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import Script from 'next/script';

export type LipSyncSource = 'none' | 'audio' | 'microphone' | 'manual';

export interface Live2DCanvasProps {
    modelPath?: string;
    className?: string;
    onLoad?: (handle?: Live2DCanvasHandle) => void;
    onError?: (error: Error) => void;
    /** Initial model position */
    initialPosition?: { x: number; y: number };
    /** Initial model scale */
    initialScale?: number;
    /** Called when model position changes */
    onPositionChange?: (position: { x: number; y: number }) => void;
    /** Called when model scale changes */
    onScaleChange?: (scale: number) => void;
    /** Enable pointer events passthrough when not on model */
    pointerPassthrough?: boolean;
    /** Called when close is requested */
    onClose?: () => void;
}

export interface Live2DCanvasHandle {
    setExpression: (expressionId: string) => void;
    setRandomExpression: () => void;
    startMotion: (group: string, index: number, priority?: number) => void;
    startRandomMotion: (group: string, priority?: number) => void;
    getModelInfo: () => { expressions: string[]; motions: { group: string; count: number }[] } | null;
    playAudioWithLipSync: (url: string) => Promise<void>;
    connectAudioForLipSync: (mediaElement: HTMLMediaElement) => Promise<void>;
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
    // Model manipulation
    getModelPosition: () => { x: number; y: number };
    setModelPosition: (x: number, y: number) => void;
    getModelScale: () => number;
    setModelScale: (scale: number) => void;
}

// Constants
const MIN_SCALE = 0.5;
const MAX_SCALE = 3.0;
const TAP_DURATION_THRESHOLD = 200;
const DRAG_DISTANCE_THRESHOLD = 5;

const Live2DCanvas = forwardRef<Live2DCanvasHandle, Live2DCanvasProps>(({
    modelPath = '/live2d/models/Haru/Haru.model3.json',
    className = '',
    onLoad,
    onError,
    initialPosition = { x: 0, y: 0 },
    initialScale = 1.0,
    onPositionChange,
    onScaleChange,
    pointerPassthrough,
    onClose,
}, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [coreLoaded, setCoreLoaded] = useState(false);
    const [isReady, setIsReady] = useState(false);
    const [error, setError] = useState<string | null>(null);
    void pointerPassthrough;

    // Instance-level state (moved from module globals to prevent HMR/multi-instance issues)
    const subdelegateRef = useRef<unknown>(null);
    const animationFrameIdRef = useRef<number | null>(null);
    const onLoadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Drag state
    const [isDragging, setIsDragging] = useState(false);
    const [isOverModel, setIsOverModel] = useState(false);
    const dragStartPos = useRef({ x: 0, y: 0 });
    const modelStartPos = useRef({ x: 0, y: 0 });
    const mouseDownTime = useRef(0);
    const mouseDownPos = useRef({ x: 0, y: 0 });
    const isPotentialTap = useRef(false);

    // Scale state
    const currentScaleRef = useRef(initialScale);
    // Kept for potential UI overlay / debugging; not currently rendered.
    const [displayScale, setDisplayScale] = useState(initialScale);
    void displayScale;

    // Model position state
    const modelPositionRef = useRef(initialPosition);

    // Get model and view from subdelegate
    const getModelAndView = useCallback(() => {
        if (!subdelegateRef.current) return null;
        const subdelegate = subdelegateRef.current as {
            getLive2DManager: () => { getModel: (index: number) => unknown } | null;
            getView: () => unknown;
        };
        const manager = subdelegate.getLive2DManager?.();
        const model = manager?.getModel(0);
        const view = subdelegate.getView?.();
        return { model, view };
    }, []);

    // Get model matrix position
    const getModelPosition = useCallback((): { x: number; y: number } => {
        const mv = getModelAndView();
        if (!mv?.model) return modelPositionRef.current;
        const model = mv.model as { _modelMatrix?: { getArray: () => number[] } };
        if (model._modelMatrix) {
            const matrix = model._modelMatrix.getArray();
            return { x: matrix[12], y: matrix[13] };
        }
        return modelPositionRef.current;
    }, [getModelAndView]);

    // Set model matrix position
    const setModelPosition = useCallback((x: number, y: number) => {
        const mv = getModelAndView();
        if (!mv?.model) return;
        const model = mv.model as { _modelMatrix?: { getArray: () => number[]; setMatrix: (m: number[]) => void } };
        if (model._modelMatrix) {
            const matrix = [...model._modelMatrix.getArray()];
            matrix[12] = x;
            matrix[13] = y;
            model._modelMatrix.setMatrix(matrix);
            modelPositionRef.current = { x, y };
            onPositionChange?.({ x, y });
        }
    }, [getModelAndView, onPositionChange]);

    // Get model scale from view matrix
    const getModelScale = useCallback((): number => {
        if (!subdelegateRef.current) return currentScaleRef.current;
        const subdelegate = subdelegateRef.current as { getScale?: () => number };
        const scale = subdelegate.getScale?.() ?? currentScaleRef.current;
        return scale;
    }, []);

    // Set model scale by adjusting view matrix
    const setModelScale = useCallback((scale: number) => {
        // This method is kept for API compatibility but scaling should be done via wheel
        const currentScale = getModelScale();
        if (currentScale === scale) return;
        currentScaleRef.current = scale;
        setDisplayScale(scale);
        onScaleChange?.(scale);
    }, [getModelScale, onScaleChange]);

    // Check if point is on model
    const isPointOnModel = useCallback((screenX: number, screenY: number): boolean => {
        const mv = getModelAndView();
        if (!mv?.model || !mv?.view) return false;

        const canvas = canvasRef.current;
        if (!canvas) return false;

        const view = mv.view as { _deviceToScreen?: { transformX: (x: number) => number; transformY: (y: number) => number } };
        if (!view._deviceToScreen) return false;

        // Scale coordinates like the reference implementation
        const scale = canvas.width / canvas.clientWidth;
        const scaledX = screenX * scale;
        const scaledY = screenY * scale;
        const modelX = view._deviceToScreen.transformX(scaledX);
        const modelY = view._deviceToScreen.transformY(scaledY);

        const model = mv.model as {
            anyhitTest?: (x: number, y: number) => string | null;
            isHitOnModel?: (x: number, y: number) => boolean;
            anyHitTestWithFallback?: (x: number, y: number) => boolean;
        };

        // Try the combined method first
        if (model.anyHitTestWithFallback) {
            return model.anyHitTestWithFallback(modelX, modelY);
        }

        // Fallback to individual methods
        const hitArea = model.anyhitTest?.(modelX, modelY);
        const isHit = model.isHitOnModel?.(modelX, modelY);
        return hitArea != null || isHit === true;
    }, [getModelAndView]);

    // Handle pointer down
    const handlePointerDown = useCallback((e: React.PointerEvent) => {
        if (!isReady) return;
        const canvas = canvasRef.current;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Only respond if clicking on model
        if (!isPointOnModel(x, y)) {
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        mouseDownTime.current = Date.now();
        mouseDownPos.current = { x: e.clientX, y: e.clientY };
        isPotentialTap.current = true;
        setIsDragging(false);

        // Store initial positions
        dragStartPos.current = { x, y };
        modelStartPos.current = getModelPosition();

        // Capture pointer
        canvas.setPointerCapture(e.pointerId);
    }, [isReady, isPointOnModel, getModelPosition]);

    // Window-level mouse move listener - for hit detection when canvas has pointer-events: none
    useEffect(() => {
        if (!isReady) return;

        const handleWindowMouseMove = (e: MouseEvent) => {
            const canvas = canvasRef.current;
            if (!canvas) return;

            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            // Check if within canvas bounds
            if (x < 0 || x > rect.width || y < 0 || y > rect.height) {
                if (isOverModel) setIsOverModel(false);
                return;
            }

            // Update hover state for pointer-events
            const onModel = isPointOnModel(x, y);
            if (onModel !== isOverModel) {
                setIsOverModel(onModel);
            }
        };

        window.addEventListener('mousemove', handleWindowMouseMove);
        return () => window.removeEventListener('mousemove', handleWindowMouseMove);
    }, [isReady, isPointOnModel, isOverModel]);

    // Handle pointer move on canvas - for dragging
    const handlePointerMove = useCallback((e: React.PointerEvent) => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Check if we should start dragging
        if (isPotentialTap.current) {
            const deltaX = e.clientX - mouseDownPos.current.x;
            const deltaY = e.clientY - mouseDownPos.current.y;
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
            const elapsed = Date.now() - mouseDownTime.current;

            if (distance > DRAG_DISTANCE_THRESHOLD || (elapsed > TAP_DURATION_THRESHOLD && distance > 1)) {
                isPotentialTap.current = false;
                setIsDragging(true);
            }
        }

        // Continue dragging
        if (isDragging) {
            e.preventDefault();
            const mv = getModelAndView();
            if (!mv?.view) return;
            const view = mv.view as { _deviceToScreen?: { transformX: (x: number) => number; transformY: (y: number) => number } };
            if (!view._deviceToScreen) return;

            const scale = canvas.width / canvas.clientWidth;

            // Convert start and current positions to model space
            const startScaledX = dragStartPos.current.x * scale;
            const startScaledY = dragStartPos.current.y * scale;
            const startModelX = view._deviceToScreen.transformX(startScaledX);
            const startModelY = view._deviceToScreen.transformY(startScaledY);

            const currentScaledX = x * scale;
            const currentScaledY = y * scale;
            const currentModelX = view._deviceToScreen.transformX(currentScaledX);
            const currentModelY = view._deviceToScreen.transformY(currentScaledY);

            const dx = currentModelX - startModelX;
            const dy = currentModelY - startModelY;

            setModelPosition(modelStartPos.current.x + dx, modelStartPos.current.y + dy);
        }
    }, [isDragging, getModelAndView, setModelPosition]);

    // Handle pointer up
    const handlePointerUp = useCallback((e: React.PointerEvent) => {
        const canvas = canvasRef.current;
        if (canvas) {
            canvas.releasePointerCapture(e.pointerId);
        }

        if (isDragging) {
            setIsDragging(false);
            modelStartPos.current = getModelPosition();
        } else if (isPotentialTap.current) {
            // It was a tap - trigger motion based on hit area
            const elapsed = Date.now() - mouseDownTime.current;
            const deltaX = e.clientX - mouseDownPos.current.x;
            const deltaY = e.clientY - mouseDownPos.current.y;
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

            if (elapsed < TAP_DURATION_THRESHOLD && distance < DRAG_DISTANCE_THRESHOLD) {
                const mv = getModelAndView();
                if (mv?.model && mv?.view && canvas) {
                    const view = mv.view as { _deviceToScreen?: { transformX: (x: number) => number; transformY: (y: number) => number } };
                    if (view._deviceToScreen) {
                        const rect = canvas.getBoundingClientRect();
                        const x = e.clientX - rect.left;
                        const y = e.clientY - rect.top;
                        const scale = canvas.width / canvas.clientWidth;
                        const modelX = view._deviceToScreen.transformX(x * scale);
                        const modelY = view._deviceToScreen.transformY(y * scale);

                        const model = mv.model as {
                            hitTest?: (area: string, x: number, y: number) => boolean;
                            setRandomExpression?: () => void;
                            startRandomMotion?: (group: string, priority: number) => void;
                        };

                        // Check hit areas - Head triggers expression, Body triggers motion
                        if (model.hitTest?.('Head', modelX, modelY)) {
                            model.setRandomExpression?.();
                        } else if (model.hitTest?.('Body', modelX, modelY)) {
                            model.startRandomMotion?.('TapBody', 2);
                        } else {
                            // Fallback: any tap triggers random motion
                            model.startRandomMotion?.('Tap', 2);
                        }
                    }
                }
            }
        }

        isPotentialTap.current = false;
    }, [isDragging, getModelPosition, getModelAndView]);

    // Handle wheel for scaling - scale model matrix directly to keep center position
    const handleWheel = useCallback((e: WheelEvent) => {
        if (!isReady) return;
        const canvas = canvasRef.current;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Only scale if on model
        if (!isPointOnModel(x, y)) return;

        e.preventDefault();

        const mv = getModelAndView();
        if (!mv?.model) return;

        const model = mv.model as {
            _modelMatrix?: {
                getArray: () => number[];
                setMatrix: (m: number[]) => void;
            };
        };

        if (!model._modelMatrix) return;

        // Get current matrix
        const matrix = model._modelMatrix.getArray();

        // Current scale is stored in matrix[0] (scaleX) - assuming uniform scale
        const currentScale = matrix[0];

        // Calculate new scale
        const scaleFactor = e.deltaY < 0 ? 1.1 : 0.9; // deltaY < 0 means scroll up = zoom in
        let newScale = currentScale * scaleFactor;

        // Clamp scale
        newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScale));

        // Only update if scale actually changed
        if (Math.abs(newScale - currentScale) < 0.001) return;

        // Scale the matrix - only scale components, preserve position
        // matrix[0] = scaleX, matrix[5] = scaleY (for uniform scaling)
        // matrix[12] = translateX, matrix[13] = translateY (position stays same)
        const newMatrix = [...matrix];
        const scaleRatio = newScale / currentScale;
        newMatrix[0] *= scaleRatio;
        newMatrix[5] *= scaleRatio;

        model._modelMatrix.setMatrix(newMatrix);

        // Update display
        currentScaleRef.current = newScale;
        setDisplayScale(newScale);
        onScaleChange?.(newScale);
    }, [isReady, isPointOnModel, getModelAndView, onScaleChange]);

    // Expose handle methods
    const canvasHandle: Live2DCanvasHandle = {
        setExpression: (expressionId: string) => {
            const mv = getModelAndView();
            if (!mv?.model) return;
            const model = mv.model as { setExpression?: (id: string) => void };
            model.setExpression?.(expressionId);
        },
        setRandomExpression: () => {
            const mv = getModelAndView();
            if (!mv?.model) return;
            const model = mv.model as { setRandomExpression?: () => void };
            model.setRandomExpression?.();
        },
        startMotion: (group: string, index: number, priority?: number) => {
            const mv = getModelAndView();
            if (!mv?.model) return;
            const model = mv.model as { startMotion?: (g: string, i: number, p: number) => void };
            model.startMotion?.(group, index, priority ?? 3);
        },
        startRandomMotion: (group: string, priority?: number) => {
            const mv = getModelAndView();
            if (!mv?.model) return;
            const model = mv.model as { startRandomMotion?: (g: string, p: number) => void };
            model.startRandomMotion?.(group, priority ?? 3);
        },
        getModelInfo: () => {
            const mv = getModelAndView();
            if (!mv?.model) return null;
            const model = mv.model as { _modelSetting?: { _json?: { FileReferences?: { Expressions?: unknown[]; Motions?: Record<string, unknown[]> } } } };
            const setting = model._modelSetting;
            if (!setting?._json?.FileReferences) return null;
            const expressions = (setting._json.FileReferences.Expressions || []).map((e: unknown, i: number) =>
                (e as { Name?: string })?.Name || `expression_${i}`
            );
            const motions: { group: string; count: number }[] = [];
            const motionGroups = setting._json.FileReferences.Motions || {};
            for (const group in motionGroups) {
                motions.push({ group, count: (motionGroups[group] as unknown[]).length });
            }
            return { expressions, motions };
        },
        playAudioWithLipSync: async (url: string) => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { playAudioWithLipSync?: (url: string) => Promise<void> };
            await subdelegate.playAudioWithLipSync?.(url);
        },
        connectAudioForLipSync: async (mediaElement: HTMLMediaElement) => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { connectAudioForLipSync?: (el: HTMLMediaElement) => Promise<void> };
            await subdelegate.connectAudioForLipSync?.(mediaElement);
        },
        startMicrophoneLipSync: async () => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { startMicrophoneLipSync?: () => Promise<void> };
            await subdelegate.startMicrophoneLipSync?.();
        },
        stopLipSync: async () => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { stopLipSync?: () => Promise<void> };
            await subdelegate.stopLipSync?.();
        },
        pauseLipSync: () => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { pauseLipSync?: () => void };
            subdelegate.pauseLipSync?.();
        },
        resumeLipSync: () => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { resumeLipSync?: () => void };
            subdelegate.resumeLipSync?.();
        },
        isLipSyncActive: () => {
            if (!subdelegateRef.current) return false;
            const subdelegate = subdelegateRef.current as { isLipSyncActive?: () => boolean };
            return subdelegate.isLipSyncActive?.() ?? false;
        },
        getLipSyncSource: () => {
            if (!subdelegateRef.current) return 'none';
            const subdelegate = subdelegateRef.current as { getLipSyncSource?: () => LipSyncSource };
            return subdelegate.getLipSyncSource?.() ?? 'none';
        },
        setLipSyncSmoothing: (value: number) => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { setLipSyncSmoothing?: (v: number) => void };
            subdelegate.setLipSyncSmoothing?.(value);
        },
        setLipSyncGain: (value: number) => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { setLipSyncGain?: (v: number) => void };
            subdelegate.setLipSyncGain?.(value);
        },
        setLipSyncValue: (value: number) => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { setLipSyncValue?: (v: number) => void };
            subdelegate.setLipSyncValue?.(value);
        },
        setOnLipSyncAudioEnded: (callback: (() => void) | null) => {
            if (!subdelegateRef.current) return;
            const subdelegate = subdelegateRef.current as { setOnLipSyncAudioEnded?: (cb: (() => void) | null) => void };
            subdelegate.setOnLipSyncAudioEnded?.(callback);
        },
        getLipSyncValue: () => {
            if (!subdelegateRef.current) return 0;
            const subdelegate = subdelegateRef.current as { getLipSyncValue?: () => number };
            return subdelegate.getLipSyncValue?.() ?? 0;
        },
        getModelPosition,
        setModelPosition,
        getModelScale,
        setModelScale,
    };

    useImperativeHandle(ref, () => canvasHandle);

    // Core script load handler
    const handleCoreLoad = useCallback(() => {
        setCoreLoaded(true);
    }, []);

    const handleCoreError = useCallback(() => {
        setError('Failed to load Live2D Core');
        onError?.(new Error('Failed to load Live2D Core'));
    }, [onError]);

    // Store callbacks in refs to avoid triggering re-initialization
    const onLoadRef = useRef(onLoad);
    const onErrorRef = useRef(onError);
    const initialPositionRef = useRef(initialPosition);
    const initialScaleRef = useRef(initialScale);

    const setModelPositionRef = useRef(setModelPosition);
    const setModelScaleRef = useRef(setModelScale);

    useEffect(() => { onLoadRef.current = onLoad; }, [onLoad]);
    useEffect(() => { onErrorRef.current = onError; }, [onError]);
    useEffect(() => { initialPositionRef.current = initialPosition; }, [initialPosition]);
    useEffect(() => { initialScaleRef.current = initialScale; }, [initialScale]);
    useEffect(() => { setModelPositionRef.current = setModelPosition; }, [setModelPosition]);
    useEffect(() => { setModelScaleRef.current = setModelScale; }, [setModelScale]);

    // Track initialization state to prevent multiple initializations
    const isInitializingRef = useRef(false);
    const isInitializedRef = useRef(false);

    // Initialize Live2D when core is loaded
    useEffect(() => {
        if (!coreLoaded) return;
        // Prevent multiple initializations
        if (isInitializingRef.current || isInitializedRef.current) return;

        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container) return;

        isInitializingRef.current = true;

        const initLive2D = async () => {
            try {
                const LAppSubdelegateModule = await import('@/lib/live2d/demo/lappsubdelegate');
                const LAppSubdelegate = LAppSubdelegateModule.LAppSubdelegate;

                // Get container dimensions
                const rect = container.getBoundingClientRect();
                const width = rect.width || window.innerWidth;
                const height = rect.height || window.innerHeight;

                // Set canvas size
                const dpr = window.devicePixelRatio || 1;
                canvas.width = Math.round(width * dpr);
                canvas.height = Math.round(height * dpr);
                canvas.style.width = `${width}px`;
                canvas.style.height = `${height}px`;

                // Clean up previous instance
                if (subdelegateRef.current) {
                    const prev = subdelegateRef.current as { release?: () => void };
                    prev.release?.();
                    subdelegateRef.current = null;
                }

                if (animationFrameIdRef.current !== null) {
                    cancelAnimationFrame(animationFrameIdRef.current);
                    animationFrameIdRef.current = null;
                }

                // Create and initialize subdelegate
                const subdelegate = new LAppSubdelegate();
                if (!subdelegate.initialize(canvas)) {
                    throw new Error('Failed to initialize LAppSubdelegate');
                }

                subdelegateRef.current = subdelegate;

                // Load model via Live2DManager
                // modelPath is like '/live2d/models/Haru/Haru.model3.json'
                // Need to split into directory path and filename
                const pathParts = modelPath.split('/');
                const modelFileName = pathParts.pop() || '';
                const modelDir = pathParts.join('/') + '/';
                const manager = subdelegate.getLive2DManager();
                manager.loadModelByPath(modelDir, modelFileName);

                isInitializedRef.current = true;
                isInitializingRef.current = false;

                // Start render loop (with safety check for model loading)
                let modelReady = false;
                const render = () => {
                    if (subdelegateRef.current) {
                        try {
                            const mgr = (subdelegateRef.current as { getLive2DManager: () => { getModel: (i: number) => { getModel: () => unknown } | null } }).getLive2DManager();
                            const lappModel = mgr?.getModel(0);

                            // Check if the internal CubismModel is actually loaded
                            const cubismModel = lappModel?.getModel?.();

                            if (cubismModel) {
                                // Model is fully loaded, safe to update
                                (subdelegateRef.current as { update: () => void }).update();

                                // First time model is ready
                                if (!modelReady) {
                                    modelReady = true;
                                    setIsReady(true);

                                    // Apply initial position and scale after model is ready
                                    onLoadTimeoutRef.current = setTimeout(() => {
                                        // Guard: skip if component unmounted
                                        if (!subdelegateRef.current) return;

                                        const pos = initialPositionRef.current;
                                        if (pos.x !== 0 || pos.y !== 0) {
                                            setModelPositionRef.current(pos.x, pos.y);
                                        }

                                        // Apply initial scale to model matrix
                                        const targetScale = initialScaleRef.current;
                                        const mgr = (subdelegateRef.current as { getLive2DManager: () => { getModel: (i: number) => unknown } } | null)?.getLive2DManager();
                                        const lappModel = mgr?.getModel(0);
                                        if (lappModel) {
                                            const model = lappModel as {
                                                _modelMatrix?: {
                                                    getArray: () => number[];
                                                    setMatrix: (m: number[]) => void;
                                                };
                                            };
                                            if (model._modelMatrix) {
                                                const matrix = [...model._modelMatrix.getArray()];
                                                const currentScale = matrix[0];
                                                // Apply ratio to scale from current to target
                                                if (Math.abs(currentScale - targetScale) > 0.001) {
                                                    const scaleRatio = targetScale / currentScale;
                                                    matrix[0] *= scaleRatio;
                                                    matrix[5] *= scaleRatio;
                                                    model._modelMatrix.setMatrix(matrix);
                                                }
                                            }
                                        }
                                        currentScaleRef.current = targetScale;
                                        setDisplayScale(targetScale);
                                        onLoadRef.current?.(canvasHandle);
                                    }, 100);
                                }
                            }
                        } catch {
                            // Model not ready yet, skip this frame
                        }
                    }
                    animationFrameIdRef.current = requestAnimationFrame(render);
                };
                render();
            } catch (err) {
                isInitializingRef.current = false;
                const message = err instanceof Error ? err.message : 'Unknown error';
                setError(message);
                onErrorRef.current?.(err instanceof Error ? err : new Error(message));
            }
        };

        initLive2D();

        return () => {
            // Full cleanup on unmount - release subdelegate and cancel animation
            if (onLoadTimeoutRef.current !== null) {
                clearTimeout(onLoadTimeoutRef.current);
                onLoadTimeoutRef.current = null;
            }
            if (animationFrameIdRef.current !== null) {
                cancelAnimationFrame(animationFrameIdRef.current);
                animationFrameIdRef.current = null;
            }
            if (subdelegateRef.current) {
                const subdelegate = subdelegateRef.current as { release?: () => void };
                subdelegate.release?.();
                subdelegateRef.current = null;
            }
            // Reset state on unmount
            isInitializedRef.current = false;
            isInitializingRef.current = false;
        };
    }, [coreLoaded, modelPath]);

    // Handle resize
    useEffect(() => {
        const container = containerRef.current;
        const canvas = canvasRef.current;
        if (!container || !canvas) return;

        const handleResize = () => {
            const rect = container.getBoundingClientRect();
            const width = rect.width || window.innerWidth;
            const height = rect.height || window.innerHeight;

            // Only set CSS size - don't set canvas.width/height here
            // Setting canvas.width/height clears the canvas content (WebGL behavior)
            // Let lappsubdelegate.ts handle the actual canvas dimensions via its ResizeObserver
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;
        };

        const observer = new ResizeObserver(handleResize);
        observer.observe(container);
        window.addEventListener('resize', handleResize);

        return () => {
            observer.disconnect();
            window.removeEventListener('resize', handleResize);
        };
    }, []);

    // Add wheel event listener
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        canvas.addEventListener('wheel', handleWheel, { passive: false });
        return () => canvas.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);

    const getCursor = () => {
        if (isDragging) return 'grabbing';
        if (isOverModel) return 'grab';
        return 'default';
    };

    return (
        <div
            ref={containerRef}
            className={`live2d-canvas ${className}`}
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                width: '100vw',
                height: '100vh',
                pointerEvents: 'none',
                zIndex: 40,
            }}
        >
            {/* Load Live2D Core */}
            <Script
                src="/live2d/core/live2dcubismcore.min.js"
                onLoad={handleCoreLoad}
                onError={handleCoreError}
                strategy="afterInteractive"
            />

            {/* Canvas - pointer-events dynamic based on whether mouse is over model */}
            <canvas
                ref={canvasRef}
                style={{
                    display: 'block',
                    background: 'transparent',
                    cursor: getCursor(),
                    pointerEvents: (isOverModel || isDragging) ? 'auto' : 'none',
                }}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerLeave={handlePointerUp}
            />


            {/* Error display */}
            {error && (
                <div
                    style={{
                        position: 'absolute',
                        bottom: '10px',
                        left: '10px',
                        color: '#ff4444',
                        fontSize: '12px',
                        background: 'rgba(0,0,0,0.6)',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        zIndex: 10,
                    }}
                >
                    Error: {error}
                </div>
            )}


            {/* Close button */}
            {onClose && isReady && (
                <button
                    onClick={onClose}
                    style={{
                        position: 'absolute',
                        top: '10px',
                        right: '10px',
                        width: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        border: 'none',
                        background: 'rgba(0,0,0,0.6)',
                        color: '#fff',
                        fontSize: '14px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        pointerEvents: 'auto',
                        transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,0,0,0.7)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.6)')}
                    title="Close Live2D"
                >
                    ×
                </button>
            )}
        </div>
    );
});

Live2DCanvas.displayName = 'Live2DCanvas';

export default Live2DCanvas;
