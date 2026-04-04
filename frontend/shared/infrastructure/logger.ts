/**
 * Unified Logger for DeepLecture Frontend
 *
 * Provides structured logging with:
 * - Environment-aware output (dev: console, prod: silent or external)
 * - Consistent format across the application
 * - Performance timing utilities
 * - Error context enrichment
 */

import { toError } from "@/lib/utils/errorUtils";
import { isAPIError } from "@/lib/api/errors";

type LogLevel = "debug" | "info" | "warn" | "error";

interface LogContext {
    component?: string;
    action?: string;
    videoId?: string;
    [key: string]: unknown;
}

interface LogEntry {
    level: LogLevel;
    message: string;
    timestamp: string;
    context?: LogContext;
    error?: Error;
}

const LOG_LEVELS: Record<LogLevel, number> = {
    debug: 0,
    info: 1,
    warn: 2,
    error: 3,
};

class Logger {
    private minLevel: LogLevel;
    private isDev: boolean;

    constructor() {
        this.isDev = process.env.NODE_ENV === "development";
        this.minLevel = this.isDev ? "debug" : "warn";
    }

    private getEffectiveLevel(level: LogLevel, error?: Error): LogLevel {
        if (level !== "error" || !error) {
            return level;
        }

        if (isAPIError(error)) {
            if (error.isCancelled()) {
                return "debug";
            }

            if (error.isClientError()) {
                return "warn";
            }
        }

        return level;
    }

    private shouldLog(level: LogLevel): boolean {
        return LOG_LEVELS[level] >= LOG_LEVELS[this.minLevel];
    }

    private formatEntry(entry: LogEntry): string {
        const { level, message, timestamp, context } = entry;
        const contextStr = context
            ? ` [${Object.entries(context)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(" ")}]`
            : "";
        return `[${timestamp}] ${level.toUpperCase()}${contextStr}: ${message}`;
    }

    private log(
        level: LogLevel,
        message: string,
        context?: LogContext,
        error?: Error
    ): void {
        const effectiveLevel = this.getEffectiveLevel(level, error);
        if (!this.shouldLog(effectiveLevel)) return;

        const entry: LogEntry = {
            level: effectiveLevel,
            message,
            timestamp: new Date().toISOString(),
            context,
            error,
        };

        const formatted = this.formatEntry(entry);

        switch (effectiveLevel) {
            case "debug":
                console.debug(formatted, context || "");
                break;
            case "info":
                console.info(formatted, context || "");
                break;
            case "warn":
                console.warn(formatted, context || "");
                break;
            case "error":
                console.error(formatted, error || context || "");
                if (error?.stack) {
                    console.error(error.stack);
                }
                break;
        }
    }

    debug(message: string, context?: LogContext): void {
        this.log("debug", message, context);
    }

    info(message: string, context?: LogContext): void {
        this.log("info", message, context);
    }

    warn(message: string, context?: LogContext): void {
        this.log("warn", message, context);
    }

    error(message: string, error?: Error, context?: LogContext): void {
        this.log("error", message, context, error);
    }

    /**
     * Create a scoped logger with preset context
     */
    scope(component: string): ScopedLogger {
        return new ScopedLogger(this, component);
    }

    /**
     * Measure and log execution time
     */
    time<T>(label: string, fn: () => T, context?: LogContext): T {
        const start = performance.now();
        try {
            const result = fn();
            const duration = performance.now() - start;
            this.debug(`${label} completed`, {
                ...context,
                durationMs: Math.round(duration * 100) / 100,
            });
            return result;
        } catch (error) {
            const duration = performance.now() - start;
            this.error(
                `${label} failed`,
                toError(error),
                { ...context, durationMs: Math.round(duration * 100) / 100 }
            );
            throw error;
        }
    }

    /**
     * Measure and log async execution time
     */
    async timeAsync<T>(
        label: string,
        fn: () => Promise<T>,
        context?: LogContext
    ): Promise<T> {
        const start = performance.now();
        try {
            const result = await fn();
            const duration = performance.now() - start;
            this.debug(`${label} completed`, {
                ...context,
                durationMs: Math.round(duration * 100) / 100,
            });
            return result;
        } catch (error) {
            const duration = performance.now() - start;
            this.error(
                `${label} failed`,
                toError(error),
                { ...context, durationMs: Math.round(duration * 100) / 100 }
            );
            throw error;
        }
    }
}

class ScopedLogger {
    constructor(
        private parent: Logger,
        private component: string
    ) {}

    debug(message: string, context?: Omit<LogContext, "component">): void {
        this.parent.debug(message, { ...context, component: this.component });
    }

    info(message: string, context?: Omit<LogContext, "component">): void {
        this.parent.info(message, { ...context, component: this.component });
    }

    warn(message: string, context?: Omit<LogContext, "component">): void {
        this.parent.warn(message, { ...context, component: this.component });
    }

    error(
        message: string,
        error?: Error,
        context?: Omit<LogContext, "component">
    ): void {
        this.parent.error(message, error, {
            ...context,
            component: this.component,
        });
    }

    time<T>(
        label: string,
        fn: () => T,
        context?: Omit<LogContext, "component">
    ): T {
        return this.parent.time(label, fn, {
            ...context,
            component: this.component,
        });
    }

    async timeAsync<T>(
        label: string,
        fn: () => Promise<T>,
        context?: Omit<LogContext, "component">
    ): Promise<T> {
        return this.parent.timeAsync(label, fn, {
            ...context,
            component: this.component,
        });
    }
}

export const logger = new Logger();

export type { LogContext, LogLevel };
