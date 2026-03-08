"use client";

import { useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { VideoUpload } from "@/components/video/VideoUpload";
import { VideoList } from "@/components/video/VideoList";
import { ProjectSidebar } from "@/components/projects/ProjectSidebar";

export default function Home() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);

  // Read project from URL, null = "All"
  const selectedProjectId = searchParams.get("project") || null;

  const handleSelectProject = useCallback(
    (projectId: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (projectId) {
        params.set("project", projectId);
      } else {
        params.delete("project");
      }
      const query = params.toString();
      router.replace(query ? `/?${query}` : "/", { scroll: false });
    },
    [searchParams, router]
  );

  const handleUploadSuccess = () => {
    setRefreshTrigger((prev) => prev + 1);
    setSidebarRefresh((prev) => prev + 1);
  };

  return (
    <div className="flex gap-6 items-start">
      <ProjectSidebar
        selectedProjectId={selectedProjectId}
        onSelectProject={handleSelectProject}
        refreshTrigger={sidebarRefresh}
      />

      <div className="flex-1 min-w-0 space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Course Subtitle & Notes
          </h1>
          <p className="text-muted-foreground">
            Upload your course videos to generate subtitles and AI-powered notes.
          </p>
        </div>

        <VideoUpload onUploadSuccess={handleUploadSuccess} />

        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-foreground">
            Your Videos
          </h2>
          <VideoList
            refreshTrigger={refreshTrigger}
            projectId={selectedProjectId}
          />
        </div>
      </div>
    </div>
  );
}
