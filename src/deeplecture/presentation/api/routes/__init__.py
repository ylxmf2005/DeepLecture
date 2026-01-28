"""Route blueprints for API layer."""

from deeplecture.presentation.api.routes.cheatsheet import bp as cheatsheet_bp
from deeplecture.presentation.api.routes.config import bp as config_bp
from deeplecture.presentation.api.routes.content import bp as content_bp
from deeplecture.presentation.api.routes.conversation import bp as conversation_bp
from deeplecture.presentation.api.routes.conversation import summaries_bp
from deeplecture.presentation.api.routes.explanation import bp as explanation_bp
from deeplecture.presentation.api.routes.fact_verification import bp as fact_verification_bp
from deeplecture.presentation.api.routes.generation import bp as generation_bp
from deeplecture.presentation.api.routes.live2d import bp as live2d_bp
from deeplecture.presentation.api.routes.media import bp as media_bp
from deeplecture.presentation.api.routes.note import bp as note_bp
from deeplecture.presentation.api.routes.quiz import bp as quiz_bp
from deeplecture.presentation.api.routes.screenshot import bp as screenshot_bp
from deeplecture.presentation.api.routes.subtitle import bp as subtitle_bp
from deeplecture.presentation.api.routes.task import bp as task_bp
from deeplecture.presentation.api.routes.timeline import bp as timeline_bp
from deeplecture.presentation.api.routes.upload import bp as upload_bp
from deeplecture.presentation.api.routes.voiceover import bp as voiceover_bp

__all__ = [
    "cheatsheet_bp",
    "config_bp",
    "content_bp",
    "conversation_bp",
    "explanation_bp",
    "fact_verification_bp",
    "generation_bp",
    "live2d_bp",
    "media_bp",
    "note_bp",
    "quiz_bp",
    "screenshot_bp",
    "subtitle_bp",
    "summaries_bp",
    "task_bp",
    "timeline_bp",
    "upload_bp",
    "voiceover_bp",
]
