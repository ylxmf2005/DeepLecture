from __future__ import annotations


from deeplecture.services.ask_service import AskService
from deeplecture.services.content_service import ContentService
from deeplecture.services.note_service import NoteService
from deeplecture.storage.artifact_registry import ArtifactRegistry
from deeplecture.storage.fs_ask_storage import AskStorage
from deeplecture.storage.fs_note_storage import NoteStorage
from deeplecture.storage.metadata_storage import ContentMetadata, MetadataStorage


class _FakeLLM:
    def generate_response(self, prompt: str, system_prompt=None, image_path=None):
        return "answer"


def _build_content_service(tmp_path, video_id: str) -> tuple[ContentService, MetadataStorage]:
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()

    metadata_storage = MetadataStorage(metadata_folder=str(outputs / "metadata"))
    artifact_registry = ArtifactRegistry(registry_folder=str(outputs / "artifacts"))

    service = ContentService(
        metadata_storage=metadata_storage,
        artifact_registry=artifact_registry,
        upload_folder=str(uploads),
        output_folder=str(outputs),
    )

    video_path = uploads / f"{video_id}.mp4"
    video_path.write_bytes(b"video")
    now = "2025-01-01T00:00:00Z"
    metadata_storage.save(
        ContentMetadata(
            id=video_id,
            type="video",
            original_filename=f"{video_id}.mp4",
            created_at=now,
            updated_at=now,
            source_file=str(video_path),
            video_file=str(video_path),
        )
    )

    return service, metadata_storage


def test_note_service_roundtrip(tmp_path) -> None:
    content_service, _ = _build_content_service(tmp_path, "video1")
    storage = NoteStorage(path_resolver=content_service)

    # Inject a fake LLM factory so we don't hit real models or require TTS config.
    class _FakeLLMFactory:
        @staticmethod
        def get_llm_for_task(task_name: str):
            return _FakeLLM()

    service = NoteService(
        storage=storage,
        content_service=content_service,
        llm_factory=_FakeLLMFactory(),
    )

    dto = service.save_note("video1", "hello")
    assert dto.content == "hello"
    assert dto.updated_at is not None

    loaded = service.get_note("video1")
    assert loaded.content == "hello"


def test_ask_service_conversation_and_qa(tmp_path) -> None:
    content_service, metadata_storage = _build_content_service(tmp_path, "video1")
    storage = AskStorage(path_resolver=content_service)
    # Inject a fake LLM factory so we don't hit real models in tests.
    class _FakeLLMFactory:
        @staticmethod
        def get_llm():
            return _FakeLLM()

    service = AskService(
        storage=storage,
        metadata_storage=metadata_storage,
        content_service=content_service,
        llm_factory=_FakeLLMFactory(),
    )

    created = service.create_conversation("video1", "Test chat")
    assert created["id"]
    items = service.list_conversations("video1")
    assert len(items) == 1

    answer = service.ask_video(
        video_id="video1",
        conversation_id=created["id"],
        question="hi",
        context_items=[],
    )
    assert answer == "answer"

    convo = service.get_conversation("video1", created["id"])
    assert convo is not None
    assert len(convo["messages"]) == 3  # greeting + user + assistant

    assert service.delete_conversation("video1", created["id"]) is True
