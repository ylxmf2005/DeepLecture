"""Interface definitions (Protocols) for Use Cases layer."""

# Storage
from deeplecture.use_cases.interfaces.ask import AskStorageProtocol

# Audio Processing
from deeplecture.use_cases.interfaces.audio import AudioProcessorProtocol
from deeplecture.use_cases.interfaces.cheatsheet import CheatsheetStorageProtocol

# Events
from deeplecture.use_cases.interfaces.events import EventPublisherProtocol

# Explanation
from deeplecture.use_cases.interfaces.explanation import ExplanationStorageProtocol

# Fact Verification
from deeplecture.use_cases.interfaces.fact_verification import (
    ClaudeCodeProtocol,
    FactVerificationStorageProtocol,
)

# Runtime Providers (Model/Prompt Selection)
from deeplecture.use_cases.interfaces.llm_provider import LLMModelInfo, LLMProviderProtocol
from deeplecture.use_cases.interfaces.note import NoteStorageProtocol

# Execution / parallelism
from deeplecture.use_cases.interfaces.parallel import ParallelGroup, ParallelRunnerProtocol

# Path Resolution
from deeplecture.use_cases.interfaces.path import PathResolverProtocol

# PDF Processing
from deeplecture.use_cases.interfaces.pdf import PdfRendererProtocol, PdfTextExtractorProtocol
from deeplecture.use_cases.interfaces.prompt_registry import (
    PromptBuilder,
    PromptInfo,
    PromptRegistryProtocol,
    PromptSpec,
)

# Quiz
from deeplecture.use_cases.interfaces.quiz import QuizStorageProtocol

# External Services
from deeplecture.use_cases.interfaces.services import ASRProtocol, LLMProtocol, TTSProtocol
from deeplecture.use_cases.interfaces.storage import (
    ArtifactStorageProtocol,
    MetadataStorageProtocol,
)
from deeplecture.use_cases.interfaces.subtitle import SubtitleStorageProtocol

# Task Management
from deeplecture.use_cases.interfaces.task import (
    TaskContextProtocol,
    TaskQueueProtocol,
)
from deeplecture.use_cases.interfaces.timeline import TimelineStorageProtocol
from deeplecture.use_cases.interfaces.tts_provider import TTSModelInfo, TTSProviderProtocol

# Upload Services
from deeplecture.use_cases.interfaces.upload import (
    FileStorageProtocol,
    PDFMergerProtocol,
    VideoDownloaderProtocol,
    VideoMergerProtocol,
)

# Video Processing
from deeplecture.use_cases.interfaces.video import VideoProcessorProtocol

__all__ = [
    "ASRProtocol",
    "ArtifactStorageProtocol",
    "AskStorageProtocol",
    "AudioProcessorProtocol",
    "CheatsheetStorageProtocol",
    "ClaudeCodeProtocol",
    "EventPublisherProtocol",
    "ExplanationStorageProtocol",
    "FactVerificationStorageProtocol",
    "FileStorageProtocol",
    "LLMModelInfo",
    "LLMProtocol",
    "LLMProviderProtocol",
    "MetadataStorageProtocol",
    "NoteStorageProtocol",
    "PDFMergerProtocol",
    "ParallelGroup",
    "ParallelRunnerProtocol",
    "PathResolverProtocol",
    "PdfRendererProtocol",
    "PdfTextExtractorProtocol",
    "PromptBuilder",
    "PromptInfo",
    "PromptRegistryProtocol",
    "PromptSpec",
    "QuizStorageProtocol",
    "SubtitleStorageProtocol",
    "TTSModelInfo",
    "TTSProtocol",
    "TTSProviderProtocol",
    "TaskContextProtocol",
    "TaskQueueProtocol",
    "TimelineStorageProtocol",
    "VideoDownloaderProtocol",
    "VideoMergerProtocol",
    "VideoProcessorProtocol",
]
