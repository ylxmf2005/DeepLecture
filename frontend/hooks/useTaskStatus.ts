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
    updated_at?: string;
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
    const hasEverConnectedRef = useRef(false);
    const maxInitialRetries = 3;  // Retries when never connected
    const maxReconnectRetries = 10;  // Retries after successful connection

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
        let isCleanedUp = false;  // Prevent error handling after cleanup (StrictMode safe)

        // Only reset refs when contentId actually changes, not on StrictMode re-runs
        // We check if this is a fresh connection by comparing with current state
        hasEverConnectedRef.current = false;
        retryCountRef.current = 0;

        const connect = () => {
            if (isCleanedUp) return;  // Don't connect if already cleaned up

            if (eventSource) {
                eventSource.close();
            }

            // Direct connection to Flask backend, bypassing Next.js proxy
            const url = `${API_BASE_URL}/api/task/stream/${contentId}`;
            eventSource = new EventSource(url);

            eventSource.onopen = () => {
                if (isCleanedUp) return;  // Ignore if cleaned up
                log.debug('SSE connected', { url });
                setIsConnected(true);
                retryCountRef.current = 0;
                hasEverConnectedRef.current = true;
            };

            eventSource.onmessage = (event) => {
                if (isCleanedUp) return;  // Ignore if cleaned up
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
                if (isCleanedUp) return;  // Ignore errors after cleanup (StrictMode triggers this)

                setIsConnected(false);
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }

                // Use different retry limits based on whether we ever connected
                const maxRetries = hasEverConnectedRef.current ? maxReconnectRetries : maxInitialRetries;

                if (retryCountRef.current < maxRetries) {
                    const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
                    log.debug('SSE reconnecting', { delay, attempt: retryCountRef.current + 1, maxRetries, everConnected: hasEverConnectedRef.current });
                    retryCountRef.current += 1;
                    retryTimeout = setTimeout(connect, delay);
                } else if (!hasEverConnectedRef.current) {
                    // Only log error if we never successfully connected
                    log.error('SSE connection failed', new Error('SSE connection failed'), { contentId, maxRetries });
                } else {
                    // Connection was working but lost - just log as warning
                    log.warn('SSE connection lost after reconnect attempts', { contentId });
                }
            };
        };

        connect();

        return () => {
            isCleanedUp = true;  // Mark as cleaned up before closing
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
