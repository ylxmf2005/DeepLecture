"""Data Transfer Objects for Use Cases layer."""

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
    "ClipPlan",
    "EnhanceTranslateRequest",
    # Subtitle
    "GenerateSubtitleRequest",
    # Voiceover
    "GenerateVoiceoverRequest",
    "ImportJobResult",
    "ImportVideoFromURLRequest",
    "MergePDFsRequest",
    "MergeVideosRequest",
    "PageWorkPlan",
    # Slide Lecture
    "SlideGenerationRequest",
    "SlideGenerationResult",
    "SubtitleResult",
    "TranscriptPage",
    "TranscriptSegment",
    "UploadPDFRequest",
    "UploadResult",
    # Upload
    "UploadVideoRequest",
    "VoiceoverResult",
]
