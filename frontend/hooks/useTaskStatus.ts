import { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '@/lib/api';

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

    useEffect(() => {
        if (!contentId) {
            setIsConnected(false);
            setTasks({});
            return;
        }

        let eventSource: EventSource | null = null;
        let retryTimeout: NodeJS.Timeout | null = null;

        const connect = () => {
            if (eventSource) {
                eventSource.close();
            }

            // Direct connection to Flask backend, bypassing Next.js proxy
            const url = `${API_BASE_URL}/api/events/${contentId}`;
            eventSource = new EventSource(url);

            eventSource.onopen = () => {
                console.log(`SSE connected directly to ${url}`);
                setIsConnected(true);
                retryCountRef.current = 0;
            };

            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const { event: eventType, task } = data;

                    console.log(`[SSE] Received event: ${eventType}, task type: ${task?.type}, status: ${task?.status}`);

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
                    console.error('Failed to parse SSE message:', err);
                }
            };

            eventSource.onerror = (err) => {
                console.error('SSE error:', err);
                setIsConnected(false);
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }

                if (retryCountRef.current < maxRetries) {
                    const delay = 1000 * Math.pow(2, retryCountRef.current);
                    console.log(`Retrying SSE connection in ${delay}ms... (Attempt ${retryCountRef.current + 1}/${maxRetries})`);
                    retryCountRef.current += 1;
                    retryTimeout = setTimeout(connect, delay);
                } else {
                    console.error('Max SSE retries reached. Connection failed.');
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
