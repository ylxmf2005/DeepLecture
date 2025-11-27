'use client';

import { useRef, useState, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react';
import dynamic from 'next/dynamic';
import { GripVertical, X, Maximize2, Minimize2 } from 'lucide-react';
import type { LipSyncSource } from './Live2DViewer';

const Live2DViewer = dynamic(() => import('./Live2DViewer'), { ssr: false });

export interface Live2DOverlayProps {
    modelPath: string;
    position: { x: number; y: number };
    size: { width: number; height: number };
    onPositionChange: (position: { x: number; y: number }) => void;
    onSizeChange: (size: { width: number; height: number }) => void;
    onClose?: () => void;
}

export interface Live2DOverlayHandle {
    setExpression: (expressionId: string) => void;
    setRandomExpression: () => void;
    startMotion: (group: string, index: number, priority?: number) => void;
    startRandomMotion: (group: string, priority?: number) => void;
    getModelInfo: () => { expressions: string[]; motions: { group: string; count: number }[] } | null;
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

const MIN_WIDTH = 200;
const MIN_HEIGHT = 250;
const MAX_WIDTH = 800;
const MAX_HEIGHT = 900;

const Live2DOverlay = forwardRef<Live2DOverlayHandle, Live2DOverlayProps>(({
    modelPath,
    position,
    size,
    onPositionChange,
    onSizeChange,
    onClose,
}, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const live2dRef = useRef<Live2DOverlayHandle>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [isResizing, setIsResizing] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const dragOffset = useRef({ x: 0, y: 0 });
    const resizeStart = useRef({ x: 0, y: 0, width: 0, height: 0 });

    useImperativeHandle(ref, () => ({
        setExpression: (expressionId: string) => live2dRef.current?.setExpression(expressionId),
        setRandomExpression: () => live2dRef.current?.setRandomExpression(),
        startMotion: (group: string, index: number, priority?: number) =>
            live2dRef.current?.startMotion(group, index, priority),
        startRandomMotion: (group: string, priority?: number) =>
            live2dRef.current?.startRandomMotion(group, priority),
        getModelInfo: () => live2dRef.current?.getModelInfo() ?? null,
        playAudioWithLipSync: async (url: string) => live2dRef.current?.playAudioWithLipSync(url),
        connectAudioForLipSync: async (audioElement: HTMLAudioElement) =>
            live2dRef.current?.connectAudioForLipSync(audioElement),
        startMicrophoneLipSync: async () => live2dRef.current?.startMicrophoneLipSync(),
        stopLipSync: async () => live2dRef.current?.stopLipSync(),
        pauseLipSync: () => live2dRef.current?.pauseLipSync(),
        resumeLipSync: () => live2dRef.current?.resumeLipSync(),
        isLipSyncActive: () => live2dRef.current?.isLipSyncActive() ?? false,
        getLipSyncSource: () => live2dRef.current?.getLipSyncSource() ?? 'none',
        setLipSyncSmoothing: (value: number) => live2dRef.current?.setLipSyncSmoothing(value),
        setLipSyncGain: (value: number) => live2dRef.current?.setLipSyncGain(value),
        setLipSyncValue: (value: number) => live2dRef.current?.setLipSyncValue(value),
        setOnLipSyncAudioEnded: (callback: (() => void) | null) =>
            live2dRef.current?.setOnLipSyncAudioEnded(callback),
        getLipSyncValue: () => live2dRef.current?.getLipSyncValue() ?? 0,
    }));

    const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
        e.preventDefault();
        const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
        const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

        dragOffset.current = {
            x: clientX - position.x,
            y: clientY - position.y,
        };
        setIsDragging(true);
    }, [position]);

    const handleResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
        e.preventDefault();
        e.stopPropagation();
        const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
        const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

        resizeStart.current = {
            x: clientX,
            y: clientY,
            width: size.width,
            height: size.height,
        };
        setIsResizing(true);
    }, [size]);

    useEffect(() => {
        if (!isDragging && !isResizing) return;

        const handleMove = (e: MouseEvent | TouchEvent) => {
            const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
            const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

            if (isDragging) {
                const newX = Math.max(0, Math.min(window.innerWidth - size.width, clientX - dragOffset.current.x));
                const newY = Math.max(0, Math.min(window.innerHeight - size.height, clientY - dragOffset.current.y));
                onPositionChange({ x: newX, y: newY });
            }

            if (isResizing) {
                const deltaX = clientX - resizeStart.current.x;
                const deltaY = clientY - resizeStart.current.y;
                const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, resizeStart.current.width + deltaX));
                const newHeight = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, resizeStart.current.height + deltaY));
                onSizeChange({ width: newWidth, height: newHeight });
            }
        };

        const handleEnd = () => {
            setIsDragging(false);
            setIsResizing(false);
        };

        window.addEventListener('mousemove', handleMove);
        window.addEventListener('mouseup', handleEnd);
        window.addEventListener('touchmove', handleMove);
        window.addEventListener('touchend', handleEnd);

        return () => {
            window.removeEventListener('mousemove', handleMove);
            window.removeEventListener('mouseup', handleEnd);
            window.removeEventListener('touchmove', handleMove);
            window.removeEventListener('touchend', handleEnd);
        };
    }, [isDragging, isResizing, size, onPositionChange, onSizeChange]);

    return (
        <div
            ref={containerRef}
            className="fixed z-50 select-none"
            style={{
                left: position.x,
                top: position.y,
                width: isMinimized ? 48 : size.width,
                height: isMinimized ? 48 : size.height,
            }}
        >
            {/* Header bar */}
            <div
                className="absolute top-0 left-0 right-0 h-8 bg-gray-800/80 backdrop-blur-sm rounded-t-lg flex items-center justify-between px-2 cursor-move z-10"
                onMouseDown={handleDragStart}
                onTouchStart={handleDragStart}
            >
                <div className="flex items-center gap-1 text-gray-300">
                    <GripVertical className="w-4 h-4" />
                    <span className="text-xs font-medium">Live2D</span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => setIsMinimized(!isMinimized)}
                        className="p-1 rounded hover:bg-gray-700/50 text-gray-300 hover:text-white transition-colors"
                    >
                        {isMinimized ? <Maximize2 className="w-3 h-3" /> : <Minimize2 className="w-3 h-3" />}
                    </button>
                    {onClose && (
                        <button
                            onClick={onClose}
                            className="p-1 rounded hover:bg-red-500/50 text-gray-300 hover:text-white transition-colors"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    )}
                </div>
            </div>

            {/* Live2D content */}
            {!isMinimized && (
                <>
                    <div
                        className="absolute top-8 left-0 right-0 bottom-0 overflow-hidden rounded-b-lg bg-transparent"
                        style={{ pointerEvents: 'auto' }}
                    >
                        <Live2DViewer
                            ref={live2dRef}
                            modelPath={modelPath}
                            width={size.width}
                            height={size.height - 32}
                            className="rounded-b-lg"
                        />
                    </div>

                    {/* Resize handle */}
                    <div
                        className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize z-20"
                        onMouseDown={handleResizeStart}
                        onTouchStart={handleResizeStart}
                    >
                        <svg
                            className="w-4 h-4 text-gray-400"
                            viewBox="0 0 24 24"
                            fill="currentColor"
                        >
                            <path d="M22 22H20V20H22V22ZM22 18H20V16H22V18ZM18 22H16V20H18V22ZM22 14H20V12H22V14ZM18 18H16V16H18V18ZM14 22H12V20H14V22Z" />
                        </svg>
                    </div>
                </>
            )}
        </div>
    );
});

Live2DOverlay.displayName = 'Live2DOverlay';

export default Live2DOverlay;
