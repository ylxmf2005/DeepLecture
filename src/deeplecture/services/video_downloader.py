import logging
import os
from typing import Dict, Any

import yt_dlp

logger = logging.getLogger(__name__)

class VideoDownloader:
    """
    Service for downloading videos using yt-dlp.
    """

    def __init__(self, output_folder: str):
        self.output_folder = output_folder

    def download_video(self, url: str, output_filename: str) -> Dict[str, Any]:
        """
        Download a video from a URL.
        
        Args:
            url: The URL of the video.
            output_filename: The desired filename (without extension).
            
        Returns:
            Dict containing:
            - success: bool
            - filepath: str (absolute path to downloaded file)
            - title: str (original video title)
            - duration: int (in seconds)
            - error: str (if failed)
        """
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # Prefer MP4
            'outtmpl': os.path.join(self.output_folder, f'{output_filename}.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first
                info = ydl.extract_info(url, download=True)
                
                # Get the actual filename
                filename = ydl.prepare_filename(info)
                
                return {
                    "success": True,
                    "filepath": filename,
                    "title": info.get('title', 'Unknown Title'),
                    "duration": info.get('duration', 0),
                    "source_type": self._detect_source_type(url)
                }
                
        except Exception as e:
            logger.error(f"Failed to download video from {url}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _detect_source_type(self, url: str) -> str:
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        if "bilibili.com" in url:
            return "bilibili"
        return "web"
