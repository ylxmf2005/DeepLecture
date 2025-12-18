import type { NextConfig } from "next";

const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL || "http://localhost:11393";

const nextConfig: NextConfig = {
  reactCompiler: true,
  async rewrites() {
    // Only rewrite static asset paths that need to work as relative paths in markdown.
    // All API calls go directly to Flask backend (configured in lib/api.ts).
    return [
      {
        source: '/screenshots/:videoId/:filename',
        destination: `${API_ORIGIN}/api/content/:videoId/screenshots/:filename`,
      },
      {
        // Notes markdown uses ../notes_assets/<videoId>/<filename> so that
        // exported .md files can load images from disk via relative paths.
        // In the web app we map this to the same screenshot-serving API.
        source: '/notes_assets/:videoId/:filename',
        destination: `${API_ORIGIN}/api/content/:videoId/screenshots/:filename`,
      },
    ];
  },
};

export default nextConfig;
