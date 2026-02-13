import { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '@/lib/api';
import { logger } from '@/shared/infrastructure';
import { toError } from '@/lib/utils/errorUtils';
import { normalizeTaskType } from '@/lib/taskTypes';

const log = logger.scope('TaskStatus');

export interface TaskStatus {
    id?: string;
    task_id: string;
    type: string;
    content_id?: string;
    contentId?: string;
    status: 'pending' | 'processing' | 'ready' | 'error';
    progress: number;
    result_path?: string;
    error?: string;
    _eventType?: string; // "initial" for history, "update" for live events
}

interface UseTaskStatusReturn {
    tasks: Record<string, TaskStatus>;
    isConnected: boolean;
}

export function useTaskStatus(contentId: string | null): UseTaskStatusReturn {
    const [tasks, setTasks] = useState<Record<string, TaskStatus>>({});
    const [isConnected, setIsConnected] = useState(false);
    const prevContentIdRef = useRef<string | null>(null);

    // Always reset task cache when switching content to avoid cross-content bleed.
    useEffect(() => {
        if (prevContentIdRef.current !== contentId) {
            prevContentIdRef.current = contentId;
            // eslint-disable-next-line react-hooks/set-state-in-effect -- Prop-driven reset on content switch
            setTasks({});
            setIsConnected(false);
        }
    }, [contentId]);

    useEffect(() => {
        if (!contentId) {
            return;
        }

        // Direct connection to Flask backend, bypassing Next.js proxy
        const url = `${API_BASE_URL}/api/task/stream/${contentId}`;
        const eventSource = new EventSource(url);

        eventSource.onopen = () => {
            log.debug('SSE connected', { url });
            setIsConnected(true);
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const { event: eventType, task } = data;

                log.debug('SSE event received', { eventType, taskType: task?.type, status: task?.status });

                if (task) {
                    const eventContentId = task.content_id ?? task.contentId;
                    if (eventContentId && eventContentId !== contentId) {
                        return;
                    }

                    const id = task.task_id || task.id;
                    if (id) {
                        const normalizedType =
                            typeof task.type === 'string' ? normalizeTaskType(task.type) : task.type;
                        setTasks(prev => ({
                            ...prev,
                            [id]: { ...task, type: normalizedType, task_id: id, _eventType: eventType }
                        }));
                    }
                }
            } catch (err) {
                log.error('Failed to parse SSE message', toError(err));
            }
        };

        eventSource.onerror = () => {
            log.warn('SSE connection error, browser will auto-reconnect', { contentId });
            // Let native EventSource reconnect via retry: frame from server.
            // Only update connection state for UI; don't manually close/reopen.
            setIsConnected(false);
        };

        return () => {
            eventSource.close();
            setIsConnected(false);
        };
    }, [contentId]);

    return { tasks, isConnected };
}
