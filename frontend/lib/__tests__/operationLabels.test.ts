import { describe, it, expect } from 'vitest';
import { getOperationNotificationLabel, OPERATION_LABELS } from '@/lib/operationLabels';

describe('OPERATION_LABELS', () => {
    it('contains labels for core non-task operations', () => {
        expect(OPERATION_LABELS.content_delete).toBeDefined();
        expect(OPERATION_LABELS.content_rename).toBeDefined();
        expect(OPERATION_LABELS.voiceover_delete).toBeDefined();
        expect(OPERATION_LABELS.voiceover_rename).toBeDefined();
        expect(OPERATION_LABELS.conversation_delete).toBeDefined();
        expect(OPERATION_LABELS.conversation_message).toBeDefined();
        expect(OPERATION_LABELS.explanation_delete).toBeDefined();
    });

    it('returns known operation labels', () => {
        const labels = getOperationNotificationLabel('voiceover_rename');
        expect(labels.success).toBe('Voiceover renamed');
        expect(labels.error).toBe('Voiceover rename failed');
    });

    it('returns fallback labels for unknown operations', () => {
        const labels = getOperationNotificationLabel('dictionary_lookup');
        expect(labels.success).toBe('Dictionary Lookup completed');
        expect(labels.error).toBe('Dictionary Lookup failed');
    });

    it('returns generic fallback labels for empty operation', () => {
        const labels = getOperationNotificationLabel('');
        expect(labels.success).toBe('Operation completed');
        expect(labels.error).toBe('Operation failed');
    });
});
