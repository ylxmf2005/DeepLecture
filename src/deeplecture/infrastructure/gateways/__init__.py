"""Outbound gateways - external service implementations."""

from deeplecture.infrastructure.gateways.anthropic import AnthropicLLM
from deeplecture.infrastructure.gateways.claude_code import ClaudeCodeGateway
from deeplecture.infrastructure.gateways.ffmpeg_audio import FFmpegAudioProcessor
from deeplecture.infrastructure.gateways.ffmpeg_video import FFmpegVideoProcessor
from deeplecture.infrastructure.gateways.ffmpeg_video_merger import FFmpegVideoMerger
from deeplecture.infrastructure.gateways.openai import OpenAILLM
from deeplecture.infrastructure.gateways.pdfium_merger import PdfiumMerger
from deeplecture.infrastructure.gateways.pdfium_processor import PdfiumRenderer, PdfiumTextExtractor
from deeplecture.infrastructure.gateways.tts import EdgeTTS, FishAudioTTS
from deeplecture.infrastructure.gateways.whisper import WhisperASR
from deeplecture.infrastructure.gateways.ytdlp_downloader import YtdlpDownloader

__all__ = [
    "AnthropicLLM",
    "ClaudeCodeGateway",
    "EdgeTTS",
    "FFmpegAudioProcessor",
    "FFmpegVideoMerger",
    "FFmpegVideoProcessor",
    "FishAudioTTS",
    "OpenAILLM",
    "PdfiumMerger",
    "PdfiumRenderer",
    "PdfiumTextExtractor",
    "WhisperASR",
    "YtdlpDownloader",
]
