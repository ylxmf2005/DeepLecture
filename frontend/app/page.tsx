"use client";

import { useState } from "react";
import { VideoUpload } from "@/components/video/VideoUpload";
import { VideoList } from "@/components/video/VideoList";

export default function Home() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUploadSuccess = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div className="space-y-8">
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
        <VideoList refreshTrigger={refreshTrigger} />
      </div>
    </div>
  );
}
