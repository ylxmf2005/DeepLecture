/**
 * Bookmarks APIs - CRUD operations for video bookmarks
 */

import { api } from "./client";

export interface BookmarkItem {
    id: string;
    timestamp: number;
    title: string;
    note: string;
    createdAt: string;
    updatedAt: string;
}

export interface BookmarkListResponse {
    contentId: string;
    bookmarks: BookmarkItem[];
}

export const listBookmarks = async (contentId: string): Promise<BookmarkListResponse> => {
    const response = await api.get<BookmarkListResponse>("/bookmarks", {
        params: { contentId },
    });
    return response.data;
};

export const createBookmark = async (
    contentId: string,
    timestamp: number,
    title: string,
    note: string = ""
): Promise<BookmarkItem> => {
    const response = await api.post<BookmarkItem>("/bookmarks", {
        content_id: contentId,
        timestamp,
        title,
        note,
    });
    return response.data;
};

export const updateBookmark = async (
    id: string,
    contentId: string,
    updates: Partial<Pick<BookmarkItem, "title" | "note" | "timestamp">>
): Promise<BookmarkItem> => {
    const response = await api.put<BookmarkItem>(`/bookmarks/${id}`, {
        content_id: contentId,
        ...updates,
    });
    return response.data;
};

export const deleteBookmark = async (id: string, contentId: string): Promise<void> => {
    await api.delete(`/bookmarks/${id}`, {
        params: { contentId },
    });
};
