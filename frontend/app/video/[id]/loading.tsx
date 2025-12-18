import { Loader2 } from "lucide-react";

/**
 * Loading state for video page (Next.js streaming)
 * Shows while Server Component fetches initial data
 */
export default function Loading() {
    return (
        <div className="flex h-[50vh] items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
    );
}
