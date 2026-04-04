import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { APIError } from "@/lib/api/errors";
import { logger } from "@/shared/infrastructure";

describe("logger", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    beforeEach(() => {
        warnSpy.mockClear();
        errorSpy.mockClear();
    });

    afterEach(() => {
        warnSpy.mockClear();
        errorSpy.mockClear();
    });

    it("downgrades API 4xx errors to warnings", () => {
        logger.scope("LoggerTest").error(
            "Expected client error",
            new APIError("Bad request", "BAD_REQUEST", { status: 400 })
        );

        expect(warnSpy).toHaveBeenCalledTimes(1);
        expect(errorSpy).not.toHaveBeenCalled();
    });

    it("keeps server-side failures at error level", () => {
        logger.scope("LoggerTest").error(
            "Unexpected server failure",
            new APIError("Server error", "SERVER_ERROR", { status: 500 })
        );

        expect(errorSpy).toHaveBeenCalled();
        expect(warnSpy).not.toHaveBeenCalled();
    });
});
