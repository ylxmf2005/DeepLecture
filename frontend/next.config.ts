import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  async rewrites() {
    // Only rewrite static asset paths that need to work as relative paths in markdown.
    // All API calls go directly to Flask backend (configured in lib/api.ts).
    return [
      {
        source: '/screenshots/:videoId/:filename',
        destination: 'http://localhost:11393/api/get-screenshot?video_id=:videoId&filename=:filename',
      },
      {
        // Notes markdown uses ../notes_assets/<videoId>/<filename> so that
        // exported .md files can load images from disk via relative paths.
        // In the web app we map this to the same screenshot-serving API.
        source: '/notes_assets/:videoId/:filename',
        destination: 'http://localhost:11393/api/get-screenshot?video_id=:videoId&filename=:filename',
      },
    ];
  },
};

export default nextConfig;
