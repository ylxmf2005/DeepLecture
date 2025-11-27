"""
Service layer package.

Services orchestrate application use-cases and depend on storage and
infrastructure abstractions instead of dealing with raw file-system paths.

Avoid eager imports here: several services pull in heavy dependencies
(LLM clients, subtitle pipelines). Lazy attribute loading keeps startup
light and avoids reintroducing import tangles if new modules appear.
"""

__all__ = [
    "AskService",
    "NoteService",
    "SubtitleService",
    "SlideLectureService",
    "TimelineService",
]


def __getattr__(name):
    if name == "AskService":
        from .ask_service import AskService

        return AskService
    if name == "NoteService":
        from .note_service import NoteService

        return NoteService
    if name == "SubtitleService":
        from .subtitle_service import SubtitleService

        return SubtitleService
    if name == "SlideLectureService":
        from .slide_lecture_service import SlideLectureService

        return SlideLectureService
    if name == "TimelineService":
        from .timeline_service import TimelineService

        return TimelineService
    raise AttributeError(f"module 'services' has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
