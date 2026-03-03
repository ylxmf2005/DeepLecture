import { describe, it, expect } from 'vitest';
import {
    normalizeTaskType,
    isContentRefreshTask,
    taskToProcessingAction,
    TASK_LABELS,
    getTaskNotificationLabel,
} from '@/lib/taskTypes';

describe('normalizeTaskType', () => {
    it('passes through standard task types unchanged', () => {
        expect(normalizeTaskType('subtitle_generation')).toBe('subtitle_generation');
        expect(normalizeTaskType('timeline_generation')).toBe('timeline_generation');
        expect(normalizeTaskType('quiz_generation')).toBe('quiz_generation');
    });

    it('normalizes known alias task types', () => {
        expect(normalizeTaskType('slide_lecture')).toBe('video_generation');
        expect(normalizeTaskType('voiceover')).toBe('voiceover_generation');
        expect(normalizeTaskType('subtitle_timeline')).toBe('timeline_generation');
        expect(normalizeTaskType('subtitle_enhancement')).toBe('subtitle_translation');
    });

    it('trims surrounding whitespace', () => {
        expect(normalizeTaskType('  quiz_generation  ')).toBe('quiz_generation');
    });

    it('returns unknown types as-is', () => {
        expect(normalizeTaskType('unknown_type')).toBe('unknown_type');
    });
});

describe('isContentRefreshTask', () => {
    it('returns true for content refresh task types', () => {
        expect(isContentRefreshTask('subtitle_generation')).toBe(true);
        expect(isContentRefreshTask('subtitle_translation')).toBe(true);
        expect(isContentRefreshTask('timeline_generation')).toBe(true);
        expect(isContentRefreshTask('video_generation')).toBe(true);
        expect(isContentRefreshTask('video_merge')).toBe(true);
        expect(isContentRefreshTask('video_import_url')).toBe(true);
        expect(isContentRefreshTask('pdf_merge')).toBe(true);
    });

    it('returns false for non-refresh task types', () => {
        expect(isContentRefreshTask('voiceover_generation')).toBe(false);
        expect(isContentRefreshTask('slide_explanation')).toBe(false);
        expect(isContentRefreshTask('fact_verification')).toBe(false);
        expect(isContentRefreshTask('cheatsheet_generation')).toBe(false);
        expect(isContentRefreshTask('note_generation')).toBe(false);
        expect(isContentRefreshTask('quiz_generation')).toBe(false);
        expect(isContentRefreshTask('test_paper_generation')).toBe(false);
    });

    it('returns false for unknown types', () => {
        expect(isContentRefreshTask('unknown_type')).toBe(false);
    });
});

describe('taskToProcessingAction', () => {
    it('maps subtitle_generation to generate', () => {
        expect(taskToProcessingAction('subtitle_generation')).toBe('generate');
    });

    it('maps subtitle_translation to translate', () => {
        expect(taskToProcessingAction('subtitle_translation')).toBe('translate');
    });

    it('maps video types to video', () => {
        expect(taskToProcessingAction('video_generation')).toBe('video');
        expect(taskToProcessingAction('video_merge')).toBe('video');
        expect(taskToProcessingAction('video_import_url')).toBe('video');
    });

    it('maps timeline_generation to timeline', () => {
        expect(taskToProcessingAction('timeline_generation')).toBe('timeline');
    });

    it('returns null for non-processing task types', () => {
        expect(taskToProcessingAction('voiceover_generation')).toBeNull();
        expect(taskToProcessingAction('slide_explanation')).toBeNull();
        expect(taskToProcessingAction('fact_verification')).toBeNull();
        expect(taskToProcessingAction('cheatsheet_generation')).toBeNull();
        expect(taskToProcessingAction('note_generation')).toBeNull();
        expect(taskToProcessingAction('quiz_generation')).toBeNull();
        expect(taskToProcessingAction('test_paper_generation')).toBeNull();
    });
});

describe('TASK_LABELS', () => {
    const ALL_14_TYPES = [
        'subtitle_generation',
        'subtitle_translation',
        'timeline_generation',
        'video_generation',
        'video_import_url',
        'video_merge',
        'pdf_merge',
        'voiceover_generation',
        'slide_explanation',
        'fact_verification',
        'cheatsheet_generation',
        'note_generation',
        'quiz_generation',
        'test_paper_generation',
    ];

    it('covers all known backend task types', () => {
        for (const taskType of ALL_14_TYPES) {
            expect(TASK_LABELS[taskType]).toBeDefined();
            expect(TASK_LABELS[taskType].success).toBeTruthy();
            expect(TASK_LABELS[taskType].error).toBeTruthy();
        }
    });

    it('returns known labels via getTaskNotificationLabel', () => {
        const labels = getTaskNotificationLabel('note_generation');
        expect(labels.success).toBe('Notes generated successfully');
        expect(labels.error).toBe('Note generation failed');
    });

    it('returns fallback labels for unknown task types', () => {
        const labels = getTaskNotificationLabel('custom_new_task');
        expect(labels.success).toBe('Custom New Task completed');
        expect(labels.error).toBe('Custom New Task failed');
    });

    it('returns generic fallback labels for empty task type', () => {
        const labels = getTaskNotificationLabel('');
        expect(labels.success).toBe('Task completed');
        expect(labels.error).toBe('Task failed');
    });
});
