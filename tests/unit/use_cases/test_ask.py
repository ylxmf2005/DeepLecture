"""Unit tests for AskUseCase."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deeplecture.config import AskConfig
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.ask import AskUseCase
from deeplecture.use_cases.dto.ask import (
    AskQuestionRequest,
    ContextItem,
    Conversation,
    ConversationSummary,
    CreateConversationRequest,
)


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    """Create mock metadata storage."""
    storage = MagicMock()
    # Default: content exists
    storage.exists.return_value = True
    return storage


@pytest.fixture
def mock_ask_storage() -> MagicMock:
    """Create mock ask storage."""
    return MagicMock()


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
    return MagicMock()


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM service."""
    llm = MagicMock()
    llm.complete.return_value = "This is a test answer."
    return llm


@pytest.fixture
def config() -> AskConfig:
    """Create default config."""
    return AskConfig()


@pytest.fixture
def usecase(
    mock_metadata_storage: MagicMock,
    mock_ask_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_llm: MagicMock,
    config: AskConfig,
) -> AskUseCase:
    """Create AskUseCase with mocked dependencies."""
    return AskUseCase(
        metadata_storage=mock_metadata_storage,
        ask_storage=mock_ask_storage,
        subtitle_storage=mock_subtitle_storage,
        llm=mock_llm,
        config=config,
    )


@pytest.fixture
def sample_conversation() -> Conversation:
    """Create sample conversation."""
    return Conversation(
        id="conv-123",
        content_id="test-content-id",
        title="Test Conversation",
        messages=[],
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )


class TestAskUseCaseListConversations:
    """Tests for list_conversations() method."""

    @pytest.mark.unit
    def test_list_conversations_success(
        self,
        usecase: AskUseCase,
        mock_metadata_storage: MagicMock,
        mock_ask_storage: MagicMock,
    ) -> None:
        """list_conversations() should return summaries."""
        # exists() is already True from fixture
        mock_ask_storage.list_conversations.return_value = [
            ConversationSummary(
                id="conv-1",
                title="First",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                last_message_preview="Hello...",
            ),
        ]

        result = usecase.list_conversations("test-content-id")

        assert len(result) == 1
        assert result[0].id == "conv-1"
        mock_ask_storage.list_conversations.assert_called_once_with("test-content-id")

    @pytest.mark.unit
    def test_list_conversations_content_not_found(
        self,
        usecase: AskUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """list_conversations() should raise when content missing."""
        mock_metadata_storage.exists.return_value = False

        with pytest.raises(ContentNotFoundError):
            usecase.list_conversations("nonexistent-id")


class TestAskUseCaseGetConversation:
    """Tests for get_conversation() method."""

    @pytest.mark.unit
    def test_get_conversation_success(
        self,
        usecase: AskUseCase,
        mock_ask_storage: MagicMock,
        sample_conversation: Conversation,
    ) -> None:
        """get_conversation() should return conversation."""
        # exists() is already True from fixture
        mock_ask_storage.get_conversation.return_value = sample_conversation

        result = usecase.get_conversation("test-content-id", "conv-123")

        assert result is not None
        assert result.id == "conv-123"

    @pytest.mark.unit
    def test_get_conversation_not_found(
        self,
        usecase: AskUseCase,
        mock_ask_storage: MagicMock,
    ) -> None:
        """get_conversation() should return None when not found."""
        # exists() is already True from fixture
        mock_ask_storage.get_conversation.return_value = None

        result = usecase.get_conversation("test-content-id", "nonexistent")

        assert result is None


class TestAskUseCaseCreateConversation:
    """Tests for create_conversation() method."""

    @pytest.mark.unit
    def test_create_conversation_success(
        self,
        usecase: AskUseCase,
        mock_ask_storage: MagicMock,
    ) -> None:
        """create_conversation() should create and save."""
        # exists() is already True from fixture
        request = CreateConversationRequest(
            content_id="test-content-id",
            title="New Chat",
        )
        result = usecase.create_conversation(request)

        assert result.content_id == "test-content-id"
        assert result.title == "New Chat"
        mock_ask_storage.save_conversation.assert_called_once()

    @pytest.mark.unit
    def test_create_conversation_content_not_found(
        self,
        usecase: AskUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """create_conversation() should raise when content missing."""
        mock_metadata_storage.exists.return_value = False

        request = CreateConversationRequest(
            content_id="nonexistent-id",
            title="Test",
        )

        with pytest.raises(ContentNotFoundError):
            usecase.create_conversation(request)


class TestAskUseCaseDeleteConversation:
    """Tests for delete_conversation() method."""

    @pytest.mark.unit
    def test_delete_conversation_success(
        self,
        usecase: AskUseCase,
        mock_ask_storage: MagicMock,
    ) -> None:
        """delete_conversation() should delete and return True."""
        # exists() is already True from fixture
        mock_ask_storage.delete_conversation.return_value = True

        result = usecase.delete_conversation("test-content-id", "conv-123")

        assert result is True
        mock_ask_storage.delete_conversation.assert_called_once()

    @pytest.mark.unit
    def test_delete_conversation_not_found(
        self,
        usecase: AskUseCase,
        mock_ask_storage: MagicMock,
    ) -> None:
        """delete_conversation() should return False when not found."""
        # exists() is already True from fixture
        mock_ask_storage.delete_conversation.return_value = False

        result = usecase.delete_conversation("test-content-id", "nonexistent")

        assert result is False


class TestAskUseCaseAskQuestion:
    """Tests for ask_question() method."""

    @pytest.mark.unit
    def test_ask_question_success(
        self,
        usecase: AskUseCase,
        mock_ask_storage: MagicMock,
        mock_llm: MagicMock,
        sample_conversation: Conversation,
    ) -> None:
        """ask_question() should build context, call LLM, and append messages."""
        mock_ask_storage.get_conversation.return_value = sample_conversation

        request = AskQuestionRequest(
            content_id="test-content-id",
            conversation_id="conv-123",
            question="What is the main idea?",
            context_items=[
                ContextItem(
                    type="timeline",
                    data={"title": "Intro", "content": "Overview", "start": 0.0, "end": 10.0},
                )
            ],
        )

        result = usecase.ask_question(request)

        assert result.answer == mock_llm.complete.return_value
        assert result.conversation.id == "conv-123"
        assert len(result.conversation.messages) == 2
        mock_llm.complete.assert_called_once()
