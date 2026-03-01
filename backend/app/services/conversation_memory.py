"""
Conversation memory management for RAG chat system.

Implements the ConversationMemory ABC with a sliding-window strategy
backed by DynamoDB (via ChatRepository) and LLM-based summarisation:

- The last *window_size* messages are kept in full.
- When *batch_size* unsummarised messages accumulate outside the window,
  only that batch is folded into the running summary (incremental).
- The running summary and ``summary_through_index`` are persisted in
  DynamoDB so nothing is lost across process restarts.

Error handling:
- ``add_message`` propagates DynamoDB write errors so the caller
  (ChatService) can react.
- Summarisation failures are logged but do **not** block message
  storage — the fold will be retried on the next qualifying message.
- ``get_context`` propagates read errors so the caller can fall back
  to simpler history retrieval.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.interfaces.conversation_memory import (
    ConversationContext,
    ConversationMemory,
    Message,
    MessageRole,
)
from app.core.interfaces import LLMProvider
from app.repositories.chat_repo import ChatRepository
from app.services.prompts import get_conversation_summary_prompt

logger = logging.getLogger(__name__)


def _dict_to_message(raw: dict[str, Any]) -> Message:
    """Convert a DynamoDB message dict to a domain ``Message`` object."""
    role_str = raw.get("sender") or raw.get("role", "user")
    try:
        role = MessageRole(role_str)
    except ValueError:
        role = MessageRole.USER

    ts = raw.get("timestamp")
    if isinstance(ts, str):
        timestamp = datetime.fromisoformat(ts)
    elif isinstance(ts, datetime):
        timestamp = ts
    else:
        timestamp = datetime.now(timezone.utc)

    return Message(
        role=role,
        content=raw.get("content", ""),
        timestamp=timestamp,
        message_id=raw.get("message_id"),
        token_count=raw.get("token_count"),
        sources=raw.get("sources"),
    )


class SlidingWindowMemory(ConversationMemory):
    """
    Sliding-window conversation memory with **incremental** batch
    summarisation.

    Strategy
    --------
    1. ``get_context()`` returns the running summary **plus** the last
       *window_size* messages.
    2. ``add_message()`` stores the new message and, when the number of
       unsummarised messages outside the window reaches *batch_size*,
       automatically triggers ``trigger_summarization()``.
    3. ``trigger_summarization()`` folds **only** the new batch into the
       existing running summary, then persists the updated summary and
       ``summary_through_index`` in DynamoDB — so nothing is lost on
       restart.

    Parameters
    ----------
    chat_repo:
        Repository for DynamoDB operations on chat sessions / messages.
    llm_provider:
        LLM used for summarisation (recommend Nova Micro for cost).
    window_size:
        Number of recent messages to keep in full.
    batch_size:
        Number of older messages that triggers a fold.
    """

    def __init__(
        self,
        chat_repo: ChatRepository,
        llm_provider: LLMProvider,
        window_size: int = 10,
        batch_size: int = 5,
    ) -> None:
        self.chat_repo = chat_repo
        self.llm_provider = llm_provider
        self.window_size = window_size
        self.batch_size = batch_size

    # ------------------------------------------------------------------
    # ConversationMemory interface
    # ------------------------------------------------------------------

    async def add_message(
        self,
        chat_id: str,
        role: MessageRole,
        content: str,
        sources: list[dict] | None = None,
    ) -> Message:
        """Store a message and trigger summarisation if needed."""
        # Persist via repository
        result = await self.chat_repo.add_message(
            chat_id=chat_id,
            sender=role.value,
            content=content,
            message_index=0,  # DynamoDB will use actual sequence
            sources=sources,
        )

        # Increment persisted message count
        session = await self.chat_repo.get_chat_session(chat_id)
        if session:
            new_count = (session.get("message_count") or 0) + 1
            await self.chat_repo.update_chat_session(
                chat_id, message_count=new_count,
            )

            # Check if a fold is needed
            summary_through = session.get("summary_through_index", -1)
            # Messages with indices [0 .. summary_through] are already
            # folded.  Messages [summary_through+1 .. new_count-1] exist.
            # Of those, the last *window_size* are "recent".
            unsummarised = new_count - self.window_size - (summary_through + 1)
            if unsummarised >= self.batch_size:
                try:
                    await self.trigger_summarization(chat_id, self.batch_size)
                except Exception as exc:
                    # Summarisation is best-effort — log and continue.
                    # The fold will be retried on the next qualifying
                    # message because summary_through_index was not
                    # advanced.
                    logger.error(
                        "Summarisation failed for chat %s (will retry later): %s",
                        chat_id, exc,
                    )

        return _dict_to_message(result)

    async def get_context(
        self,
        chat_id: str,
        window_size: int | None = None,
    ) -> ConversationContext:
        """Return the running summary + recent messages for LLM prompt
        construction.

        Uses the persisted ``running_summary`` from DynamoDB — no LLM
        call is made here.
        """
        effective_window = window_size if window_size is not None else self.window_size

        # Fetch chat session metadata
        session = await self.chat_repo.get_chat_session(chat_id)
        running_summary: str | None = None
        summary_through: int = -1
        if session:
            raw_summary = session.get("running_summary", "")
            running_summary = raw_summary if raw_summary else None
            summary_through = session.get("summary_through_index", -1)

        # Fetch recent messages (DynamoDB returns newest-first)
        raw_messages = await self.chat_repo.get_recent_messages(
            chat_id=chat_id, count=effective_window,
        )
        # Reverse so oldest is first (chronological order)
        raw_messages.reverse()

        messages = [_dict_to_message(m) for m in raw_messages]

        return ConversationContext(
            summary=running_summary,
            recent_messages=messages,
            summary_through_index=summary_through,
        )

    async def trigger_summarization(
        self,
        chat_id: str,
        batch_size: int | None = None,
    ) -> str | None:
        """Incrementally fold a batch of older messages into the running
        summary, then persist the result to DynamoDB.

        Only the *batch_size* oldest unsummarised messages are sent to
        the LLM — the existing summary is provided as prior context so
        the model can extend it rather than rewrite from scratch.
        """
        effective_batch = batch_size if batch_size is not None else self.batch_size

        session = await self.chat_repo.get_chat_session(chat_id)
        if not session:
            return None

        current_summary: str = session.get("running_summary", "")
        summary_through: int = session.get("summary_through_index", -1)

        # Fetch *all* messages (oldest-first) to pick the correct slice
        all_messages = await self.chat_repo.get_messages(
            chat_id=chat_id, limit=10_000,
        )

        # Slice: messages from summary_through+1 to summary_through+1+batch
        start = summary_through + 1
        end = start + effective_batch
        batch = all_messages[start:end]

        if not batch:
            return current_summary or None

        new_summary = await self._fold_batch(current_summary, batch)

        new_through = summary_through + len(batch)
        await self.chat_repo.update_chat_session(
            chat_id,
            running_summary=new_summary,
            summary_through_index=new_through,
        )

        logger.debug(
            "Folded %d messages into summary for chat %s (through index %d)",
            len(batch), chat_id, new_through,
        )
        return new_summary

    async def get_message_count(self, chat_id: str) -> int:
        """Return total message count for a chat."""
        return await self.chat_repo.get_message_count(chat_id)

    async def clear_conversation(self, chat_id: str) -> None:
        """Delete all messages and reset summary for a chat."""
        try:
            await self.chat_repo.delete_chat_messages(chat_id)
        except Exception as exc:
            logger.error(
                "Failed to delete messages for chat %s: %s", chat_id, exc,
            )
            raise

        try:
            await self.chat_repo.update_chat_session(
                chat_id,
                message_count=0,
                running_summary="",
                summary_through_index=-1,
            )
        except Exception as exc:
            logger.error(
                "Failed to reset session metadata for chat %s "
                "(messages may already be deleted): %s",
                chat_id, exc,
            )
            raise

    async def close(self) -> None:
        """No persistent connections to tear down."""
        pass

    # ------------------------------------------------------------------
    # Backwards-compat alias (used by ChatService / existing callers)
    # ------------------------------------------------------------------

    async def get_conversation_context(
        self,
        chat_id: str,
        force_refresh: bool = False,
    ) -> ConversationContext:
        """Alias for ``get_context()`` for backward compatibility.

        ``force_refresh`` is accepted but ignored — the implementation
        now reads persisted state from DynamoDB and never caches
        in-process.
        """
        return await self.get_context(chat_id, window_size=self.window_size)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fold_batch(
        self,
        existing_summary: str,
        messages: list[dict[str, Any]],
    ) -> str:
        """Fold *messages* into *existing_summary* via a single LLM call.

        If there is no prior summary the LLM simply summarises the batch.
        If a summary already exists the LLM is instructed to *extend* it
        with the new information.
        """
        if not messages:
            return existing_summary

        formatted = "\n\n".join(
            f"{(m.get('sender') or m.get('role', 'user')).upper()}: {m.get('content', '')}"
            for m in messages
        )

        summary_prompt = get_conversation_summary_prompt()

        if existing_summary:
            prompt = (
                f"{summary_prompt}\n\n"
                f"Existing summary:\n{existing_summary}\n\n"
                f"New messages to incorporate:\n\n{formatted}\n\n"
                f"Updated summary:"
            )
        else:
            prompt = (
                f"{summary_prompt}\n\n"
                f"Conversation to summarize:\n\n{formatted}\n\n"
                f"Summary:"
            )

        result = await self.llm_provider.generate(
            prompt=prompt,
            max_tokens=500,
            temperature=0.3,
        )
        return result.strip()

    # Kept for backward compatibility with older test code
    async def _summarize_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> str:
        """Summarise a list of messages from scratch (no prior summary)."""
        return await self._fold_batch("", messages)

    def clear_cache(self, chat_id: str | None = None) -> None:
        """No-op — summaries are now persisted in DynamoDB, not cached."""
        pass

    def update_window_size(self, new_size: int) -> None:
        """Update window size."""
        self.window_size = new_size
