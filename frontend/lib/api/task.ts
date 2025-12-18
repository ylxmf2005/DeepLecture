/**
 * Task APIs - Task status tracking and SSE streaming
 */

import { api, API_BASE_URL } from "./client";
import type { TaskStatusResponse, TaskListResponse } from "./types";

export const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse> => {
    const response = await api.get<TaskStatusResponse>(`/task/${taskId}`);
    return response.data;
};

export const getTasksForContent = async (contentId: string): Promise<TaskListResponse> => {
    const response = await api.get<TaskListResponse>(`/task/content/${contentId}`);
    return response.data;
};

export const createTaskEventSource = (contentId: string): EventSource => {
    return new EventSource(`${API_BASE_URL}/api/task/stream/${contentId}`);
};

/** @deprecated Use getTaskStatus instead */
export const getJobStatus = getTaskStatus;
