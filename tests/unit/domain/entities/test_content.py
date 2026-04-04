"""Unit tests for ContentMetadata entity."""

from datetime import datetime, timezone

import pytest

from deeplecture.domain.entities.content import ContentMetadata, ContentType
from deeplecture.domain.entities.feature import FeatureStatus

UTC = timezone.utc


class TestContentType:
    """Tests for ContentType enum."""

    @pytest.mark.unit
    def test_video_value(self) -> None:
        """VIDEO type should have correct value."""
        assert ContentType.VIDEO.value == "video"

    @pytest.mark.unit
    def test_slide_value(self) -> None:
        """SLIDE type should have correct value."""
        assert ContentType.SLIDE.value == "slide"


class TestContentMetadata:
    """Tests for ContentMetadata entity."""

    @pytest.fixture
    def sample_video_content(self) -> ContentMetadata:
        """Create sample video content."""
        return ContentMetadata(
            id="content-123",
            type=ContentType.VIDEO,
            original_filename="lecture.mp4",
            source_file="/data/content/content-123/source.mp4",
        )

    @pytest.fixture
    def sample_slide_content(self) -> ContentMetadata:
        """Create sample slide content."""
        return ContentMetadata(
            id="content-456",
            type=ContentType.SLIDE,
            original_filename="slides.pdf",
            source_file="/data/content/content-456/source.pdf",
            pdf_page_count=10,
        )

    @pytest.mark.unit
    def test_video_content_creation(self, sample_video_content: ContentMetadata) -> None:
        """Video content should be created with correct defaults."""
        assert sample_video_content.id == "content-123"
        assert sample_video_content.type == ContentType.VIDEO
        assert sample_video_content.original_filename == "lecture.mp4"
        assert sample_video_content.source_type == "local"

    @pytest.mark.unit
    def test_slide_content_creation(self, sample_slide_content: ContentMetadata) -> None:
        """Slide content should include page count."""
        assert sample_slide_content.type == ContentType.SLIDE
        assert sample_slide_content.pdf_page_count == 10

    @pytest.mark.unit
    def test_default_feature_statuses(self, sample_video_content: ContentMetadata) -> None:
        """All feature statuses should default to 'none'."""
        assert sample_video_content.video_status == "none"
        assert sample_video_content.subtitle_status == "none"
        assert sample_video_content.enhance_translate_status == "none"
        assert sample_video_content.timeline_status == "none"
        assert sample_video_content.notes_status == "none"
        assert sample_video_content.detected_source_language is None

    @pytest.mark.unit
    def test_detected_source_language_can_be_persisted(self, sample_video_content: ContentMetadata) -> None:
        """Detected source language should be stored on the entity."""
        sample_video_content.detected_source_language = "ja"

        assert sample_video_content.detected_source_language == "ja"

    @pytest.mark.unit
    def test_timestamps_are_utc(self, sample_video_content: ContentMetadata) -> None:
        """Timestamps should be in UTC."""
        assert sample_video_content.created_at.tzinfo is not None
        assert sample_video_content.updated_at.tzinfo is not None

    @pytest.mark.unit
    def test_type_string_coercion(self) -> None:
        """ContentType should be coerced from string."""
        content = ContentMetadata(
            id="c1",
            type="video",  # type: ignore[arg-type]
            original_filename="test.mp4",
            source_file="/test.mp4",
        )
        assert content.type == ContentType.VIDEO
        assert isinstance(content.type, ContentType)

    @pytest.mark.unit
    def test_datetime_string_coercion(self) -> None:
        """Datetime fields should accept ISO-8601 strings."""
        content = ContentMetadata(
            id="c1",
            type=ContentType.VIDEO,
            original_filename="test.mp4",
            source_file="/test.mp4",
            created_at="2025-01-01T12:00:00+00:00",  # type: ignore[arg-type]
        )
        assert isinstance(content.created_at, datetime)
        assert content.created_at.year == 2025

    @pytest.mark.unit
    def test_invalid_source_type_raises(self) -> None:
        """Invalid source_type should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid source_type"):
            ContentMetadata(
                id="c1",
                type=ContentType.VIDEO,
                original_filename="test.mp4",
                source_file="/test.mp4",
                source_type="invalid",  # type: ignore[arg-type]
            )

    @pytest.mark.unit
    def test_with_status_immutability(self, sample_video_content: ContentMetadata) -> None:
        """with_status should return new instance, not mutate."""
        original_id = id(sample_video_content)
        updated = sample_video_content.with_status("subtitle", FeatureStatus.PROCESSING)

        assert id(updated) != original_id
        assert sample_video_content.subtitle_status == "none"
        assert updated.subtitle_status == "processing"

    @pytest.mark.unit
    def test_with_status_updates_timestamp(self, sample_video_content: ContentMetadata) -> None:
        """with_status should update updated_at timestamp."""
        original_time = sample_video_content.updated_at
        updated = sample_video_content.with_status("subtitle", FeatureStatus.READY)

        assert updated.updated_at >= original_time

    @pytest.mark.unit
    def test_with_status_unknown_feature_raises(self, sample_video_content: ContentMetadata) -> None:
        """with_status should raise for unknown feature."""
        with pytest.raises(ValueError, match="Unknown feature"):
            sample_video_content.with_status("unknown_feature", FeatureStatus.READY)

    @pytest.mark.unit
    def test_with_job_id(self, sample_video_content: ContentMetadata) -> None:
        """with_job_id should set job tracking field."""
        updated = sample_video_content.with_job_id("subtitle", "job-789")

        assert sample_video_content.subtitle_job_id is None
        assert updated.subtitle_job_id == "job-789"

    @pytest.mark.unit
    def test_get_status(self, sample_video_content: ContentMetadata) -> None:
        """get_status should return correct feature status."""
        assert sample_video_content.get_status("subtitle") == "none"

        updated = sample_video_content.with_status("subtitle", FeatureStatus.READY)
        assert updated.get_status("subtitle") == "ready"

    @pytest.mark.unit
    def test_get_status_unknown_feature_raises(self, sample_video_content: ContentMetadata) -> None:
        """get_status should raise for unknown feature."""
        with pytest.raises(ValueError, match="Unknown feature"):
            sample_video_content.get_status("unknown")

    @pytest.mark.unit
    def test_source_types(self) -> None:
        """All valid source types should be accepted."""
        for source_type in ("local", "remote", "youtube", "bilibili"):
            content = ContentMetadata(
                id="c1",
                type=ContentType.VIDEO,
                original_filename="test.mp4",
                source_file="/test.mp4",
                source_type=source_type,  # type: ignore[arg-type]
            )
            assert content.source_type == source_type
