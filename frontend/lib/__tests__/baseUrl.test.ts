import { afterEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_API_URL = process.env.NEXT_PUBLIC_API_URL;
const ORIGINAL_API_PORT = process.env.NEXT_PUBLIC_API_PORT;

async function importBaseUrlModule() {
    vi.resetModules();
    return import("@/lib/api/baseUrl");
}

afterEach(() => {
    if (ORIGINAL_API_URL === undefined) {
        delete process.env.NEXT_PUBLIC_API_URL;
    } else {
        process.env.NEXT_PUBLIC_API_URL = ORIGINAL_API_URL;
    }

    if (ORIGINAL_API_PORT === undefined) {
        delete process.env.NEXT_PUBLIC_API_PORT;
    } else {
        process.env.NEXT_PUBLIC_API_PORT = ORIGINAL_API_PORT;
    }

    vi.resetModules();
});

describe("resolveApiBaseUrl", () => {
    it("uses NEXT_PUBLIC_API_URL when configured and trims trailing slash", async () => {
        process.env.NEXT_PUBLIC_API_URL = "http://127.0.0.1:2233/";
        delete process.env.NEXT_PUBLIC_API_PORT;

        const { resolveApiBaseUrl } = await importBaseUrlModule();
        expect(resolveApiBaseUrl()).toBe("http://127.0.0.1:2233");
    });

    it("falls back to deterministic localhost default", async () => {
        delete process.env.NEXT_PUBLIC_API_URL;
        process.env.NEXT_PUBLIC_API_PORT = "11393";

        const { resolveApiBaseUrl } = await importBaseUrlModule();
        expect(resolveApiBaseUrl()).toBe("http://localhost:11393");
    });
});
