export type LogMeta = Record<string, unknown>;

export interface ScopedLogger {
    debug: (message: string, meta?: LogMeta) => void;
    info: (message: string, meta?: LogMeta) => void;
    warn: (message: string, meta?: LogMeta) => void;
    error: (message: string, error?: unknown, meta?: LogMeta) => void;
}

function fmt(scope: string, message: string): string {
    return `[${scope}] ${message}`;
}

export const logger = {
    scope(scope: string): ScopedLogger {
        return {
            debug(message, meta) {
                // eslint-disable-next-line no-console
                console.debug(fmt(scope, message), meta ?? "");
            },
            info(message, meta) {
                // eslint-disable-next-line no-console
                console.info(fmt(scope, message), meta ?? "");
            },
            warn(message, meta) {
                // eslint-disable-next-line no-console
                console.warn(fmt(scope, message), meta ?? "");
            },
            error(message, error, meta) {
                // eslint-disable-next-line no-console
                console.error(fmt(scope, message), error ?? "", meta ?? "");
            },
        };
    },
};

