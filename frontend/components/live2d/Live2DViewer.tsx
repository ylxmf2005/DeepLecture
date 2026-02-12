'use client';

/**
 * Live2D Viewer Component
 * Properly integrates Live2D Cubism SDK 5 with React/Next.js
 * Supports both standard lip sync and MotionSync for advanced vowel-based lip animation
 */

import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import Script from 'next/script';
import { API_BASE_URL } from '@/lib/api';
import { logger } from '@/shared/infrastructure';
import { toError } from '@/lib/utils/errorUtils';
import type { LAppSubdelegateInterface, LipSyncSource } from '@/lib/live2d/types';

const log = logger.scope('Live2DViewer');

export interface Live2DViewerProps {
  modelPath?: string;
  width?: number;
  height?: number;
  className?: string;
  onLoad?: () => void;
  onError?: (error: Error) => void;
  /** Enable MotionSync for models that support it */
  enableMotionSync?: boolean;
}

export interface Live2DViewerHandle {
  /** Set a specific expression */
  setExpression: (expressionId: string) => void;
  /** Set a random expression */
  setRandomExpression: () => void;
  /** Play a specific motion */
  startMotion: (group: string, index: number, priority?: number) => void;
  /** Play a random motion from the given group */
  startRandomMotion: (group: string, priority?: number) => void;
  /** Get model info (expression list and motion groups) */
  getModelInfo: () => { expressions: string[]; motions: { group: string; count: number }[] } | null;

  // Lip Sync API
  /** Play an audio URL and drive lip sync */
  playAudioWithLipSync: (url: string) => Promise<void>;
  /** Connect an existing audio element for lip sync */
  connectAudioForLipSync: (audioElement: HTMLAudioElement) => Promise<void>;
  /** Start real-time lip sync from microphone input */
  startMicrophoneLipSync: () => Promise<void>;
  /** Stop lip sync */
  stopLipSync: () => Promise<void>;
  /** Pause lip-sync audio */
  pauseLipSync: () => void;
  /** Resume lip-sync audio */
  resumeLipSync: () => void;
  /** Check whether lip sync is active */
  isLipSyncActive: () => boolean;
  /** Get the lip-sync source type */
  getLipSyncSource: () => LipSyncSource;
  /** Set lip-sync smoothing (0-1) */
  setLipSyncSmoothing: (value: number) => void;
  /** Set lip-sync gain */
  setLipSyncGain: (value: number) => void;
  /** Set the lip-sync value directly (0-1) */
  setLipSyncValue: (value: number) => void;
  /** Set callback invoked when lip-sync audio ends */
  setOnLipSyncAudioEnded: (callback: (() => void) | null) => void;
  /** Get the current lip-sync value */
  getLipSyncValue: () => number;
}

// Store global instances
let subdelegateInstance: LAppSubdelegateInterface | null = null;
let animationFrameId: number | null = null;
let isFrameworkInitialized = false;
let isMotionSyncCoreLoaded = false;
let isMotionSyncInitialized = false;

const Live2DViewer = forwardRef<Live2DViewerHandle, Live2DViewerProps>(({
  modelPath = `${API_BASE_URL}/api/live2d/models/Haru/Haru.model3.json`,
  width = 800,
  height = 600,
  className = '',
  onLoad,
  onError,
  enableMotionSync = false,
}, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [coreLoaded, setCoreLoaded] = useState(false);
  const [motionSyncCoreLoaded, setMotionSyncCoreLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [debugInfo, setDebugInfo] = useState<string>('Waiting for Core...');
  const [currentScale, setCurrentScale] = useState(1.0);

  // Store current model path for change detection
  const currentModelPathRef = useRef<string>(modelPath);

  // Handle wheel event for zooming
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    if (!subdelegateInstance || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const localX = e.clientX - rect.left;
    const localY = e.clientY - rect.top;

    subdelegateInstance.onWheel?.(e.deltaY, localX, localY);
    const scale = subdelegateInstance.getScale?.() ?? 1.0;
    setCurrentScale(scale);
  }, []);

  const handlePointerDown = useCallback((e: PointerEvent) => {
    if (!subdelegateInstance || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    subdelegateInstance.onPointBeganLocal?.(e.clientX - rect.left, e.clientY - rect.top);
  }, []);

  const handlePointerMove = useCallback((e: PointerEvent) => {
    if (!subdelegateInstance || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    subdelegateInstance.onPointMovedLocal?.(e.clientX - rect.left, e.clientY - rect.top);
  }, []);

  const handlePointerUp = useCallback((e: PointerEvent) => {
    if (!subdelegateInstance || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    subdelegateInstance.onPointEndedLocal?.(e.clientX - rect.left, e.clientY - rect.top);
  }, []);

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    setExpression: (expressionId: string) => {
      subdelegateInstance?.setExpression?.(expressionId);
    },
    setRandomExpression: () => {
      subdelegateInstance?.setRandomExpression?.();
    },
    startMotion: (group: string, index: number, priority = 2) => {
      subdelegateInstance?.startMotion?.(group, index, priority);
    },
    startRandomMotion: (group: string, priority = 2) => {
      subdelegateInstance?.startRandomMotion?.(group, priority);
    },
    getModelInfo: () => {
      return subdelegateInstance?.getModelInfo?.() ?? null;
    },

    playAudioWithLipSync: async (url: string) => {
      await subdelegateInstance?.playAudioWithLipSync?.(url);
    },
    connectAudioForLipSync: async (audioElement: HTMLAudioElement) => {
      await subdelegateInstance?.connectAudioForLipSync?.(audioElement);
    },
    startMicrophoneLipSync: async () => {
      await subdelegateInstance?.startMicrophoneLipSync?.();
    },
    stopLipSync: async () => {
      await subdelegateInstance?.stopLipSync?.();
    },
    pauseLipSync: () => {
      subdelegateInstance?.pauseLipSync?.();
    },
    resumeLipSync: () => {
      subdelegateInstance?.resumeLipSync?.();
    },
    isLipSyncActive: () => {
      return subdelegateInstance?.isLipSyncActive?.() ?? false;
    },
    getLipSyncSource: (): LipSyncSource => {
      return subdelegateInstance?.getLipSyncSource?.() ?? 'none';
    },
    setLipSyncSmoothing: (value: number) => {
      subdelegateInstance?.setLipSyncSmoothing?.(value);
    },
    setLipSyncGain: (value: number) => {
      subdelegateInstance?.setLipSyncGain?.(value);
    },
    setLipSyncValue: (value: number) => {
      subdelegateInstance?.setLipSyncValue?.(value);
    },
    setOnLipSyncAudioEnded: (callback: (() => void) | null) => {
      subdelegateInstance?.setOnLipSyncAudioEnded?.(callback);
    },
    getLipSyncValue: () => {
      return subdelegateInstance?.getLipSyncValue?.() ?? 0;
    },
  }));

  // Core script load handler
  const handleCoreLoad = useCallback(() => {
    log.debug('Live2D Cubism Core loaded');
    setCoreLoaded(true);
    setDebugInfo('Core loaded, initializing...');
  }, []);

  // Core script error handler
  const handleCoreError = useCallback(() => {
    const err = new Error('Failed to load Live2D Cubism Core');
    setError(err.message);
    setDebugInfo('Core load failed!');
    onError?.(err);
  }, [onError]);

  // MotionSync Core script load handler
  const handleMotionSyncCoreLoad = useCallback(() => {
    log.debug('Live2D MotionSync Core loaded');
    isMotionSyncCoreLoaded = true;
    setMotionSyncCoreLoaded(true);
    setDebugInfo('MotionSync Core loaded');
  }, []);

  // MotionSync Core script error handler (non-fatal)
  const handleMotionSyncCoreError = useCallback(() => {
    log.warn('MotionSync Core not loaded - advanced lip sync unavailable');
    isMotionSyncCoreLoaded = false;
    setMotionSyncCoreLoaded(false);
  }, []);

  // Initialize Live2D
  useEffect(() => {
    if (!coreLoaded || !canvasRef.current) return;

    const canvas = canvasRef.current;

    // Check if Core is available
    const win = window as unknown as { Live2DCubismCore?: unknown };
    if (typeof win.Live2DCubismCore === 'undefined') {
      setError('Live2D Cubism Core not available');
      setDebugInfo('Core not found in window');
      return;
    }

    setDebugInfo('Initializing Live2D Framework...');

    // Dynamically import the demo modules
    const initLive2D = async () => {
      try {
        // Import framework and demo modules
        const { CubismFramework, Option, LogLevel } = await import('@/lib/live2d/live2dcubismframework');
        const { LAppPal } = await import('@/lib/live2d/demo/lapppal');
        const { LAppSubdelegate } = await import('@/lib/live2d/demo/lappsubdelegate');
        // Initialize Cubism Framework (only once)
        if (!isFrameworkInitialized) {
          LAppPal.updateTime();

          const cubismOption = new Option();
          cubismOption.logFunction = (msg: string) => log.debug(`[Live2D] ${msg}`);
          cubismOption.loggingLevel = LogLevel.LogLevel_Verbose;

          if (!CubismFramework.startUp(cubismOption)) {
            throw new Error('Failed to start Cubism Framework');
          }
          CubismFramework.initialize();
          isFrameworkInitialized = true;
          setDebugInfo('Framework initialized');

          // Initialize MotionSync Framework if Core is loaded and enabled
          if (enableMotionSync && isMotionSyncCoreLoaded && !isMotionSyncInitialized) {
            try {
              const { CubismMotionSync, MotionSyncOption } = await import('@/lib/live2d/motionsync/live2dcubismmotionsync');

              const motionSyncOption = new MotionSyncOption();
              motionSyncOption.logFunction = (msg: string) => log.debug(`[MotionSync] ${msg}`);
              motionSyncOption.loggingLevel = LogLevel.LogLevel_Verbose;

              if (CubismMotionSync.startUp(motionSyncOption)) {
                CubismMotionSync.initialize();
                isMotionSyncInitialized = true;
                log.debug('MotionSync Framework initialized');
                setDebugInfo('MotionSync initialized');
              }
            } catch (e) {
              log.warn('MotionSync initialization failed', { error: e instanceof Error ? e.message : String(e) });
            }
          }
        }

        // Clean up previous instance
        if (subdelegateInstance) {
          try {
            subdelegateInstance.release();
          } catch (e) {
            log.warn('Failed to release previous subdelegate', { error: e instanceof Error ? e.message : String(e) });
          }
          subdelegateInstance = null;
        }

        if (animationFrameId !== null) {
          cancelAnimationFrame(animationFrameId);
          animationFrameId = null;
        }

        // Set canvas size
        canvas.width = width;
        canvas.height = height;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        // Create and initialize subdelegate
        const subdelegate = new LAppSubdelegate();
        if (!subdelegate.initialize(canvas)) {
          throw new Error('Failed to initialize LAppSubdelegate');
        }

        subdelegateInstance = subdelegate;
        setDebugInfo('Subdelegate initialized, loading model...');

        // Get the live2d manager and load the model
        const live2dManager = subdelegate.getLive2DManager();

        // Parse model path to get model directory and filename
        const pathParts = modelPath.split('/');
        const modelFileName = pathParts.pop() || 'model.model3.json';
        const modelDir = pathParts.join('/') + '/';
        const modelName = modelFileName.replace('.model3.json', '');

        // Load the model by path (supports both standard and MotionSync models)
        live2dManager.loadModelByPath(modelDir, modelFileName);
        currentModelPathRef.current = modelPath;

        const isMotionSync = live2dManager.isMotionSyncModel(modelName);
        setDebugInfo(`Loading model: ${modelName}${isMotionSync ? ' (MotionSync)' : ''}`);

        // Start animation loop
        const loop = () => {
          if (!subdelegateInstance) return;

          LAppPal.updateTime();

          try {
            subdelegateInstance.update();
          } catch (e) {
            log.error('Live2D update error', toError(e));
          }

          animationFrameId = requestAnimationFrame(loop);
        };

        loop();

        // Add event listeners
        canvas.addEventListener('wheel', handleWheel, { passive: false });
        canvas.addEventListener('pointerdown', handlePointerDown);
        canvas.addEventListener('pointermove', handlePointerMove);
        canvas.addEventListener('pointerup', handlePointerUp);
        canvas.addEventListener('pointerleave', handlePointerUp);

        setIsLoading(false);
        setDebugInfo('Live2D running');
        onLoad?.();

      } catch (err) {
        log.error('Live2D initialization error', toError(err));
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        setError(errorMessage);
        setDebugInfo(`Error: ${errorMessage}`);
        onError?.(err instanceof Error ? err : new Error(errorMessage));
      }
    };

    initLive2D();

    // Cleanup
    return () => {
      if (animationFrameId !== null) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
      }
      if (canvas) {
        canvas.removeEventListener('wheel', handleWheel);
        canvas.removeEventListener('pointerdown', handlePointerDown);
        canvas.removeEventListener('pointermove', handlePointerMove);
        canvas.removeEventListener('pointerup', handlePointerUp);
        canvas.removeEventListener('pointerleave', handlePointerUp);
      }
    };
  }, [coreLoaded, motionSyncCoreLoaded, enableMotionSync, width, height, modelPath, onLoad, onError, handleWheel, handlePointerDown, handlePointerMove, handlePointerUp]);

  // Handle model path changes
  useEffect(() => {
    if (!subdelegateInstance || !coreLoaded) return;
    if (currentModelPathRef.current === modelPath) return;

    const changeModel = async () => {
      if (!subdelegateInstance) return;
      try {
        // Parse model path to get directory and filename
        const pathParts = modelPath.split('/');
        const modelFileName = pathParts.pop() || 'model.model3.json';
        const modelDir = pathParts.join('/') + '/';
        const modelName = modelFileName.replace('.model3.json', '');

        subdelegateInstance.getLive2DManager().loadModelByPath(modelDir, modelFileName);
        currentModelPathRef.current = modelPath;
        setDebugInfo(`Changed to: ${modelName}`);
      } catch (err) {
        log.error('Live2D model change error', toError(err), { modelPath });
      }
    };

    changeModel();
  }, [modelPath, coreLoaded]);

  return (
    <div className={`live2d-viewer ${className}`} style={{ position: 'relative' }}>
      {/* Load Live2D Core */}
      <Script
        src="/live2d/core/live2dcubismcore.min.js"
        onLoad={handleCoreLoad}
        onError={handleCoreError}
        strategy="afterInteractive"
      />

      {/* Load MotionSync Core (optional, for advanced lip sync) */}
      {enableMotionSync && (
        <Script
          src="/live2d/live2dcubismmotionsynccore.min.js"
          onLoad={handleMotionSyncCoreLoad}
          onError={handleMotionSyncCoreError}
          strategy="afterInteractive"
        />
      )}

      {/* Loading overlay */}
      {isLoading && !error && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: '#888',
            fontSize: '14px',
            textAlign: 'center',
            zIndex: 10,
          }}
        >
          <div>Loading Live2D...</div>
          <div style={{ fontSize: '12px', marginTop: '8px', color: '#666' }}>{debugInfo}</div>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: '#ff4444',
            fontSize: '14px',
            textAlign: 'center',
            zIndex: 10,
          }}
        >
          <div>Error: {error}</div>
          <div style={{ fontSize: '12px', marginTop: '8px', color: '#666' }}>{debugInfo}</div>
        </div>
      )}

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{
          display: 'block',
          background: 'transparent',
        }}
      />

      {/* Debug info */}
      <div
        style={{
          position: 'absolute',
          bottom: '10px',
          left: '10px',
          fontSize: '11px',
          color: '#888',
          background: 'rgba(0,0,0,0.6)',
          padding: '4px 8px',
          borderRadius: '4px',
        }}
      >
        {debugInfo} | Scale: {currentScale.toFixed(2)}
      </div>
    </div>
  );
});

Live2DViewer.displayName = 'Live2DViewer';

export default Live2DViewer;
