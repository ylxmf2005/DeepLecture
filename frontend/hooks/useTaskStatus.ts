import { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '@/lib/api';
import { logger } from '@/shared/infrastructure';
import { toError } from '@/lib/utils/errorUtils';

const log = logger.scope('TaskStatus');

export interface TaskStatus {
    id?: string;
    task_id: string;
    type: string;
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
    const retryCountRef = useRef(0);
    const maxRetries = 3;

    // Reset state when contentId becomes null (prop-driven state reset)
    useEffect(() => {
        if (contentId) return;
        // eslint-disable-next-line react-hooks/set-state-in-effect -- Prop-driven reset to avoid stale tasks when contentId clears
        setTasks({});
        if (isConnected) {

            setIsConnected(false);
        }
    }, [contentId, isConnected]);

    useEffect(() => {
        if (!contentId) {
            return;
        }

        let eventSource: EventSource | null = null;
        let retryTimeout: NodeJS.Timeout | null = null;

        const connect = () => {
            if (eventSource) {
                eventSource.close();
            }

            // Direct connection to Flask backend, bypassing Next.js proxy
            const url = `${API_BASE_URL}/api/task/stream/${contentId}`;
            eventSource = new EventSource(url);

            eventSource.onopen = () => {
                log.debug('SSE connected', { url });
                setIsConnected(true);
                retryCountRef.current = 0;
            };

            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const { event: eventType, task } = data;

                    log.debug('SSE event received', { eventType, taskType: task?.type, status: task?.status });

                    if (task) {
                        const id = task.task_id || task.id;
                        if (id) {
                            setTasks(prev => ({
                                ...prev,
                                [id]: { ...task, task_id: id, _eventType: eventType }
                            }));
                        }
                    }
                } catch (err) {
                    log.error('Failed to parse SSE message', toError(err));
                }
            };

            eventSource.onerror = () => {
                log.warn('SSE connection error', { contentId });
                setIsConnected(false);
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }

                if (retryCountRef.current < maxRetries) {
                    const delay = 1000 * Math.pow(2, retryCountRef.current);
                    log.info('Retrying SSE connection', { delay, attempt: retryCountRef.current + 1, maxRetries });
                    retryCountRef.current += 1;
                    retryTimeout = setTimeout(connect, delay);
                } else {
                    log.error('Max SSE retries reached, connection failed', new Error('SSE connection failed'), { contentId, maxRetries });
                }
            };
        };

        connect();

        return () => {
            if (eventSource) {
                eventSource.close();
            }
            if (retryTimeout) {
                clearTimeout(retryTimeout);
            }
        };
    }, [contentId]);

    return { tasks, isConnected };
}
