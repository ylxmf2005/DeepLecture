import { Suspense } from "react";
import VideoPageClient from "./VideoPageClient";
import { getContentMetadataServer, listVoiceoversServer } from "./data";
import Loading from "./loading";

interface VideoPageProps {
    params: Promise<{ id: string }>;
}

/**
 * Server Component wrapper for video page
 * Fetches initial data server-side to eliminate client waterfall
 */
async function VideoPageContent({ videoId }: { videoId: string }) {
    // Parallel fetch on server - eliminates client waterfall
    const [initialContent, initialVoiceovers] = await Promise.all([
        getContentMetadataServer(videoId),
        listVoiceoversServer(videoId),
    ]);

    return (
        <VideoPageClient
            videoId={videoId}
            initialContent={initialContent}
            initialVoiceovers={initialVoiceovers}
        />
    );
}

/**
 * Video page with Server Component data fetching
 * Uses streaming with Suspense for optimal UX
 */
export default async function VideoPage({ params }: VideoPageProps) {
    const { id: videoId } = await params;

    return (
        <Suspense fallback={<Loading />}>
            <VideoPageContent videoId={videoId} />
        </Suspense>
    );
}
