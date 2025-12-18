"use client";

import { useEffect, useRef } from "react";
import { logger } from "./logger";

/**
 * Core Web Vitals metrics
 * @see https://web.dev/vitals/
 */
interface WebVitalsMetric {
    name: "LCP" | "CLS" | "FCP" | "TTFB" | "INP";
    value: number;
    rating: "good" | "needs-improvement" | "poor";
    delta: number;
    id: string;
}

interface PerformanceMetrics {
    lcp?: number; // Largest Contentful Paint
    cls?: number; // Cumulative Layout Shift
    fcp?: number; // First Contentful Paint
    ttfb?: number; // Time to First Byte
    inp?: number; // Interaction to Next Paint
}

// Thresholds based on Google's Web Vitals recommendations
const THRESHOLDS = {
    LCP: { good: 2500, poor: 4000 },
    CLS: { good: 0.1, poor: 0.25 },
    FCP: { good: 1800, poor: 3000 },
    TTFB: { good: 800, poor: 1800 },
    INP: { good: 200, poor: 500 },
} as const;

// 60fps frame time threshold for detecting rapid re-renders
const SIXTY_FPS_FRAME_TIME_MS = 16;

function getRating(
    name: keyof typeof THRESHOLDS,
    value: number
): WebVitalsMetric["rating"] {
    const threshold = THRESHOLDS[name];
    if (value <= threshold.good) return "good";
    if (value <= threshold.poor) return "needs-improvement";
    return "poor";
}

const log = logger.scope("PerformanceMonitor");

/**
 * Reports Web Vitals metrics
 */
function reportWebVital(metric: WebVitalsMetric): void {
    const { name, value, rating, delta } = metric;

    log.info(`Web Vital: ${name}`, {
        value: Math.round(value * 100) / 100,
        rating,
        delta: Math.round(delta * 100) / 100,
    });

    // In production, could send to analytics
    // if (process.env.NODE_ENV === 'production') {
    //     sendToAnalytics(metric);
    // }
}

/**
 * Hook to measure component render performance
 */
export function useRenderPerformance(componentName: string): void {
    const renderCount = useRef(0);
    const lastRenderTime = useRef(0);
    const isInitialized = useRef(false);

    useEffect(() => {
        const now = performance.now();

        if (!isInitialized.current) {
            // First render: just initialize
            isInitialized.current = true;
            lastRenderTime.current = now;
            renderCount.current = 1;
            return;
        }

        renderCount.current += 1;
        const timeSinceLastRender = now - lastRenderTime.current;
        lastRenderTime.current = now;

        // Only log if renders are too frequent (potential performance issue)
        if (timeSinceLastRender < SIXTY_FPS_FRAME_TIME_MS) {
            log.warn(`Rapid re-render detected`, {
                component: componentName,
                renderCount: renderCount.current,
                timeSinceLastMs: Math.round(timeSinceLastRender * 100) / 100,
            });
        }
    });
}

/**
 * Hook to measure async operation performance
 */
export function useAsyncPerformance(operationName: string) {
    return {
        measure: async <T,>(fn: () => Promise<T>): Promise<T> => {
            const start = performance.now();
            try {
                const result = await fn();
                const duration = performance.now() - start;
                log.debug(`Async operation: ${operationName}`, {
                    durationMs: Math.round(duration * 100) / 100,
                    status: "success",
                });
                return result;
            } catch (error) {
                const duration = performance.now() - start;
                log.warn(`Async operation: ${operationName}`, {
                    durationMs: Math.round(duration * 100) / 100,
                    status: "error",
                });
                throw error;
            }
        },
    };
}

/**
 * Performance Monitor Component
 *
 * Automatically measures Core Web Vitals when mounted.
 * Should be placed near the root of the application.
 *
 * Usage:
 * ```tsx
 * // In layout.tsx or _app.tsx
 * <PerformanceMonitor />
 * ```
 */
export function PerformanceMonitor(): null {
    useEffect(() => {
        // Dynamically import web-vitals to avoid SSR issues
        import("web-vitals")
            .then(({ onLCP, onCLS, onFCP, onTTFB, onINP }) => {
                const createHandler =
                    (name: WebVitalsMetric["name"]) =>
                    (metric: { value: number; delta: number; id: string }) => {
                        reportWebVital({
                            name,
                            value: metric.value,
                            delta: metric.delta,
                            id: metric.id,
                            rating: getRating(name, metric.value),
                        });
                    };

                onLCP(createHandler("LCP"));
                onCLS(createHandler("CLS"));
                onFCP(createHandler("FCP"));
                onTTFB(createHandler("TTFB"));
                onINP(createHandler("INP"));

                log.info("Web Vitals monitoring initialized");
            })
            .catch((error) => {
                log.warn("Failed to load web-vitals library", {
                    error: String(error),
                });
            });
    }, []);

    return null;
}

/**
 * Utility to create a performance mark and measure
 */
export function createPerformanceMark(name: string): {
    end: () => number;
} {
    const markName = `${name}-start`;
    performance.mark(markName);

    return {
        end: () => {
            const endMarkName = `${name}-end`;
            performance.mark(endMarkName);
            const measure = performance.measure(name, markName, endMarkName);
            const duration = measure.duration;

            log.debug(`Performance mark: ${name}`, {
                durationMs: Math.round(duration * 100) / 100,
            });

            // Cleanup
            performance.clearMarks(markName);
            performance.clearMarks(endMarkName);
            performance.clearMeasures(name);

            return duration;
        },
    };
}

export type { WebVitalsMetric, PerformanceMetrics };
