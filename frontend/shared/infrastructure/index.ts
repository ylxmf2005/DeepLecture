/**
 * Shared Infrastructure Module
 *
 * Provides foundational utilities for the entire application:
 * - Logger: Unified logging with environment awareness
 * - ErrorBoundary: Graceful error handling in React components
 * - PerformanceMonitor: Web Vitals tracking and performance measurement
 */

// Logger
export { logger } from "./logger";
export type { LogContext, LogLevel } from "./logger";

// Error Boundary
export { ErrorBoundary, useErrorHandler } from "./ErrorBoundary";

// Performance Monitoring
export {
    PerformanceMonitor,
    useRenderPerformance,
    useAsyncPerformance,
    createPerformanceMark,
} from "./PerformanceMonitor";
export type { WebVitalsMetric, PerformanceMetrics } from "./PerformanceMonitor";
