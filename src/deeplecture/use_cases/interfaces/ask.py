"""Ask storage protocol - conversation persistence contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.ask import Conversation, ConversationSummary


class AskStorageProtocol(Protocol):
    """
    Conversation storage contract.

    Manages persistence of Q&A conversations.
    """

    def list_conversations(self, content_id: str) -> list[ConversationSummary]:
        """
        List all conversations for a content item.

        Args:
            content_id: Content identifier

        Returns:
            List of conversation summaries, sorted by updated_at descending
        """
        ...

    def get_conversation(self, content_id: str, conversation_id: str) -> Conversation | None:
        """
        Get a specific conversation.

        Args:
            content_id: Content identifier
            conversation_id: Conversation identifier

        Returns:
            Conversation or None if not found
        """
        ...

    def save_conversation(self, conversation: Conversation) -> None:
        """
        Save or update a conversation.

        Args:
            conversation: Conversation to save
        """
        ...

    def delete_conversation(self, content_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            content_id: Content identifier
            conversation_id: Conversation identifier

        Returns:
            True if deleted, False if not found
        """
        ...
