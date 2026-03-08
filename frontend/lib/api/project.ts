/**
 * Project APIs - CRUD and content assignment
 */

import { api } from "./client";
import type {
    Project,
    ProjectListResponse,
    CreateProjectPayload,
    UpdateProjectPayload,
} from "./types";

export const listProjects = async (): Promise<ProjectListResponse> => {
    const response = await api.get<ProjectListResponse>("/projects");
    return response.data;
};

export const createProject = async (
    payload: CreateProjectPayload
): Promise<Project> => {
    const response = await api.post<Project>("/projects", payload);
    return response.data;
};

export const updateProject = async (
    projectId: string,
    payload: UpdateProjectPayload
): Promise<Project> => {
    const response = await api.put<Project>(`/projects/${projectId}`, payload);
    return response.data;
};

export const deleteProject = async (projectId: string): Promise<void> => {
    await api.delete(`/projects/${projectId}`);
};

export const assignContentToProject = async (
    contentId: string,
    projectId: string | null
): Promise<void> => {
    await api.patch(`/content/${contentId}/project`, { projectId });
};
