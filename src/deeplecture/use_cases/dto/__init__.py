"""Data Transfer Objects for Use Cases layer."""

from deeplecture.use_cases.dto.cheatsheet import (
    CheatsheetResult,
    CheatsheetStats,
    GenerateCheatsheetRequest,
    GeneratedCheatsheetResult,
    KnowledgeItem,
    SaveCheatsheetRequest,
)
from deeplecture.use_cases.dto.quiz import (
    GeneratedQuizResult,
    GenerateQuizRequest,
    QuizItem,
    QuizResult,
    QuizStats,
    SaveQuizRequest,
)
from deeplecture.use_cases.dto.slide import (
    PageWorkPlan,
    SlideGenerationRequest,
    SlideGenerationResult,
    TranscriptPage,
    TranscriptSegment,
)
from deeplecture.use_cases.dto.subtitle import (
    BackgroundContext,
    BilingualSegment,
    EnhanceTranslateRequest,
    GenerateSubtitleRequest,
    SubtitleResult,
)
from deeplecture.use_cases.dto.upload import (
    ImportJobResult,
    ImportVideoFromURLRequest,
    MergePDFsRequest,
    MergeVideosRequest,
    UploadPDFRequest,
    UploadResult,
    UploadVideoRequest,
)
from deeplecture.use_cases.dto.voiceover import (
    AlignmentPlan,
    AudioOpKind,
    AudioOpPlan,
    ClipPlan,
    GenerateVoiceoverRequest,
    VoiceoverResult,
)

__all__ = [
    "AlignmentPlan",
    "AudioOpKind",
    "AudioOpPlan",
    "BackgroundContext",
    "BilingualSegment",
    "CheatsheetResult",
    "CheatsheetStats",
    "ClipPlan",
    "EnhanceTranslateRequest",
    "GenerateCheatsheetRequest",
    "GenerateQuizRequest",
    "GenerateSubtitleRequest",
    "GenerateVoiceoverRequest",
    "GeneratedCheatsheetResult",
    "GeneratedQuizResult",
    "ImportJobResult",
    "ImportVideoFromURLRequest",
    "KnowledgeItem",
    "MergePDFsRequest",
    "MergeVideosRequest",
    "PageWorkPlan",
    "QuizItem",
    "QuizResult",
    "QuizStats",
    "SaveCheatsheetRequest",
    "SaveQuizRequest",
    "SlideGenerationRequest",
    "SlideGenerationResult",
    "SubtitleResult",
    "TranscriptPage",
    "TranscriptSegment",
    "UploadPDFRequest",
    "UploadResult",
    "UploadVideoRequest",
    "VoiceoverResult",
]
