export interface PdfFile {
    id: string;
    file: File;
    name: string;
    size: number;
    pageCount?: number;
}

export interface VideoFile {
    id: string;
    file: File;
    name: string;
    size: number;
    duration?: number;
}

export type UploadTab = "local" | "url" | "record";
