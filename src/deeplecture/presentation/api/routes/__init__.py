"""Route blueprints for API layer."""

from deeplecture.presentation.api.routes.bookmark import bp as bookmark_bp
from deeplecture.presentation.api.routes.cheatsheet import bp as cheatsheet_bp
from deeplecture.presentation.api.routes.config import bp as config_bp
from deeplecture.presentation.api.routes.content import bp as content_bp
from deeplecture.presentation.api.routes.content_config import bp as content_config_bp
from deeplecture.presentation.api.routes.conversation import bp as conversation_bp
from deeplecture.presentation.api.routes.conversation import summaries_bp
from deeplecture.presentation.api.routes.explanation import bp as explanation_bp
from deeplecture.presentation.api.routes.fact_verification import bp as fact_verification_bp
from deeplecture.presentation.api.routes.flashcard import bp as flashcard_bp
from deeplecture.presentation.api.routes.generation import bp as generation_bp
from deeplecture.presentation.api.routes.global_config import bp as global_config_bp
from deeplecture.presentation.api.routes.live2d import bp as live2d_bp
from deeplecture.presentation.api.routes.media import bp as media_bp
from deeplecture.presentation.api.routes.note import bp as note_bp
from deeplecture.presentation.api.routes.podcast import bp as podcast_bp
from deeplecture.presentation.api.routes.project import bp as project_bp
from deeplecture.presentation.api.routes.prompt_templates import bp as prompt_templates_bp
from deeplecture.presentation.api.routes.quiz import bp as quiz_bp
from deeplecture.presentation.api.routes.read_aloud import bp as read_aloud_bp
from deeplecture.presentation.api.routes.screenshot import bp as screenshot_bp
from deeplecture.presentation.api.routes.subtitle import bp as subtitle_bp
from deeplecture.presentation.api.routes.task import bp as task_bp
from deeplecture.presentation.api.routes.test_paper import bp as test_paper_bp
from deeplecture.presentation.api.routes.timeline import bp as timeline_bp
from deeplecture.presentation.api.routes.upload import bp as upload_bp
from deeplecture.presentation.api.routes.voiceover import bp as voiceover_bp

__all__ = [
    "bookmark_bp",
    "cheatsheet_bp",
    "config_bp",
    "content_bp",
    "content_config_bp",
    "conversation_bp",
    "explanation_bp",
    "fact_verification_bp",
    "flashcard_bp",
    "generation_bp",
    "global_config_bp",
    "live2d_bp",
    "media_bp",
    "note_bp",
    "podcast_bp",
    "project_bp",
    "prompt_templates_bp",
    "quiz_bp",
    "read_aloud_bp",
    "screenshot_bp",
    "subtitle_bp",
    "summaries_bp",
    "task_bp",
    "test_paper_bp",
    "timeline_bp",
    "upload_bp",
    "voiceover_bp",
]
