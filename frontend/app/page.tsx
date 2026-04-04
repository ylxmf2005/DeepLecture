"use client";

import { useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { VideoUpload } from "@/components/video/VideoUpload";
import { VideoList } from "@/components/video/VideoList";
import { ProjectFilter } from "@/components/projects/ProjectFilter";

export default function Home() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [filterRefresh, setFilterRefresh] = useState(0);

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
    setFilterRefresh((prev) => prev + 1);
  };

  return (
    <div className="space-y-6">
      <ProjectFilter
        selectedProjectId={selectedProjectId}
        onSelectProject={handleSelectProject}
        refreshTrigger={filterRefresh}
      />

      <VideoUpload onUploadSuccess={handleUploadSuccess} />

      <VideoList
        refreshTrigger={refreshTrigger}
        projectId={selectedProjectId}
      />
    </div>
  );
}
