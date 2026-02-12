import { describe, it, expect } from 'vitest';
import { buildVideoImportErrorHint } from '@/lib/videoImportErrorHints';

describe('buildVideoImportErrorHint', () => {
    it('returns auth hint for bot/age/private restrictions', () => {
        expect(buildVideoImportErrorHint("Sign in to confirm you're not a bot")).toContain('authentication');
        expect(buildVideoImportErrorHint('This is an age-restricted video')).toContain('authentication');
        expect(buildVideoImportErrorHint('This video is private')).toContain('authentication');
    });

    it('returns cookie hint for cookie loading/decrypt failures', () => {
        const hint = buildVideoImportErrorHint('failed to load cookies from chrome');
        expect(hint).toContain('Chrome cookies could not be read');

        const hint2 = buildVideoImportErrorHint('failed to decrypt cookie (AES-GCM)');
        expect(hint2).toContain('close all Chrome windows');
    });

    it('returns null for generic errors', () => {
        expect(buildVideoImportErrorHint('network timeout')).toBeNull();
        expect(buildVideoImportErrorHint(undefined)).toBeNull();
        expect(buildVideoImportErrorHint('')).toBeNull();
    });
});
