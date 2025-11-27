"""Data Transfer Objects for DeepLecture."""

from deeplecture.dto.content import (
    ContentUploadResult,
    VideoImportJobResult,
    VideoMergeJobResult,
)
from deeplecture.dto.subtitle import (
    SubtitleGenerationResult,
    SubtitleEnhanceTranslateResult,
)
from deeplecture.dto.note import (
    NoteDTO,
    NotePart,
    GeneratedNoteResult,
    NoteGenerationJobResult,
)
from deeplecture.dto.slide import (
    SlideDeckDTO,
    SlideLectureGenerationResult,
    SlideGenerationContext,
    TranscriptSegment,
    TranscriptPage,
    TranscriptHistory,
    AudioSegmentInfo,
    PageAudioArtifacts,
    PageVideoArtifacts,
)
from deeplecture.dto.storage import (
    ArtifactRecord,
    ContentMetadata,
    ConversationRecord,
    NoteRecord,
    SubtitleRecord,
    TimelineRecord,
)

__all__ = [
    # content
    "ContentUploadResult",
    "VideoImportJobResult",
    "VideoMergeJobResult",
    # subtitle
    "SubtitleGenerationResult",
    "SubtitleEnhanceTranslateResult",
    # note
    "NoteDTO",
    "NotePart",
    "GeneratedNoteResult",
    "NoteGenerationJobResult",
    # slide
    "SlideDeckDTO",
    "SlideLectureGenerationResult",
    "SlideGenerationContext",
    "TranscriptSegment",
    "TranscriptPage",
    "TranscriptHistory",
    "AudioSegmentInfo",
    "PageAudioArtifacts",
    "PageVideoArtifacts",
    # storage records
    "ArtifactRecord",
    "ContentMetadata",
    "ConversationRecord",
    "NoteRecord",
    "SubtitleRecord",
    "TimelineRecord",
]
