"""
Chat service for orchestrating RAG pipeline.

This service coordinates:
- Message storage (ChatRepository)
- Document retrieval (RetrievalService)
- Prompt assembly (PromptBuilder)
- LLM generation (BedrockNovaProvider)
- Response persistence

Error handling strategy:
- Streaming path: all errors are caught, logged, and emitted as SSE
  ``error`` events so the client always receives a well-formed stream.
- Non-streaming path: transient AWS errors raise ``ServiceUnavailableError``;
  permanent / unexpected errors raise ``RuntimeError``.
- Retrieval and memory failures degrade gracefully (empty context / no
  summary) so the user still gets *some* answer.
"""

import logging
from typing import Any, AsyncIterator
from uuid import UUID

from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import Settings
from app.core.interfaces import LLMProvider
from app.core.interfaces.conversation_memory import ConversationMemory
from app.repositories.chat_repo import ChatRepository
from app.services.prompt_builder import PromptBuilder
from app.services.retrieval_service import RetrievalResult, RetrievalService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User-friendly error messages (never leak internal details to SSE clients)
# ---------------------------------------------------------------------------

_USER_MSG_LLM_THROTTLED = (
    "The AI service is currently experiencing high demand. "
    "Please wait a moment and try again."
)
_USER_MSG_LLM_UNAVAILABLE = (
    "The AI service is temporarily unavailable. Please try again shortly."
)
_USER_MSG_LLM_ACCESS_DENIED = (
    "The AI service could not be reached due to a configuration issue. "
    "Please contact your administrator."
)
_USER_MSG_RETRIEVAL_FAILED = (
    "There was a problem searching your documents. "
    "The assistant will answer without document context."
)
_USER_MSG_MEMORY_FAILED = (
    "There was a problem loading conversation history. "
    "The assistant will answer without prior context."
)
_USER_MSG_STORAGE_FAILED = (
    "A message could not be saved. Please try again."
)
_USER_MSG_INTERNAL = (
    "An unexpected error occurred. Please try again or contact support."
)


class ServiceUnavailableError(Exception):
    """Raised when a downstream AWS service is transiently unavailable."""


def _classify_aws_error(exc: ClientError) -> str:
    """Return a user-facing message based on the AWS error code."""
    code = exc.response["Error"]["Code"]
    if code == "ThrottlingException":
        return _USER_MSG_LLM_THROTTLED
    if code in {"AccessDeniedException", "UnrecognizedClientException"}:
        return _USER_MSG_LLM_ACCESS_DENIED
    if code in {
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelNotReadyException",
    }:
        return _USER_MSG_LLM_UNAVAILABLE
    # Default for any other AWS error
    return _USER_MSG_LLM_UNAVAILABLE


class ChatService:
    """
    Service for handling chat interactions with RAG pipeline.
    
    Orchestrates the complete flow:
    1. Store user message
    2. Retrieve relevant context from documents
    3. Build prompt with context + conversation history
    4. Generate LLM response (streaming or non-streaming)
    5. Store assistant response
    """
    
    def __init__(
        self,
        chat_repo: ChatRepository,
        retrieval_service: RetrievalService,
        prompt_builder: PromptBuilder,
        llm_provider: LLMProvider,
        settings: Settings,
        conversation_memory: ConversationMemory | None = None
    ):
        """
        Initialize chat service.
        
        Args:
            chat_repo: Repository for chat/message storage
            retrieval_service: Service for document retrieval
            prompt_builder: Service for prompt assembly
            llm_provider: Provider for LLM generation
            settings: Application settings
            conversation_memory: Optional conversation memory manager
        """
        self.chat_repo = chat_repo
        self.retrieval_service = retrieval_service
        self.prompt_builder = prompt_builder
        self.llm_provider = llm_provider
        self.settings = settings
        self.conversation_memory = conversation_memory
    
    async def process_user_message_stream(
        self,
        chat_id: str,
        project_id: UUID,
        user_message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Process user message and stream LLM response.

        This is the main method for the SSE streaming endpoint.

        Yields SSE events:
        - {"type": "token", "content": "..."}
        - {"type": "sources", "sources": [...]}
        - {"type": "done", "message_id": "..."}
        - {"type": "error", "error": "..."}

        Error handling:
        - Bedrock failures (throttling, unavailable, access denied) →
          user-friendly error SSE event.
        - Retrieval / memory failures → graceful degradation (empty
          context), logged server-side.
        - DynamoDB write failures → error SSE event with storage message.
        - All errors are logged before being sent to the client.
        """
        try:
            # Step 1: Store user message
            try:
                await self.chat_repo.add_message(
                    chat_id=chat_id,
                    sender="user",
                    content=user_message,
                    message_index=0,  # DynamoDB will use actual count
                )
            except (ClientError, EndpointConnectionError) as exc:
                logger.error(
                    "DynamoDB write failed for user message in chat %s: %s",
                    chat_id, exc,
                )
                yield {"type": "error", "error": _USER_MSG_STORAGE_FAILED}
                return
            except Exception:
                logger.exception(
                    "Unexpected error storing user message in chat %s", chat_id,
                )
                yield {"type": "error", "error": _USER_MSG_STORAGE_FAILED}
                return

            # Step 2: Retrieve relevant context (graceful degradation)
            retrieval_result = await self._retrieve_context(project_id, user_message)

            # Step 3: Get conversation history (graceful degradation)
            formatted_messages, conversation_summary = await self._get_history(
                chat_id,
            )

            # Step 4: Build prompt with context and memory
            prompt = self.prompt_builder.build_prompt(
                user_question=user_message,
                retrieved_context=retrieval_result.context,
                conversation_summary=conversation_summary,
                recent_messages=formatted_messages,
            )

            # Step 5: Stream LLM response
            accumulated_response = ""

            try:
                async for token in self.llm_provider.generate_stream(prompt):  # type: ignore[misc]
                    accumulated_response += token
                    yield {"type": "token", "content": token}
            except ClientError as exc:
                user_msg = _classify_aws_error(exc)
                logger.error(
                    "Bedrock streaming error in chat %s: %s — %s",
                    chat_id,
                    exc.response["Error"]["Code"],
                    exc,
                )
                yield {"type": "error", "error": user_msg}
                return
            except EndpointConnectionError as exc:
                logger.error(
                    "Bedrock endpoint unreachable for chat %s: %s",
                    chat_id, exc,
                )
                yield {"type": "error", "error": _USER_MSG_LLM_UNAVAILABLE}
                return
            except RuntimeError as exc:
                # BedrockNovaProvider wraps errors in RuntimeError
                err_str = str(exc).lower()
                if "throttl" in err_str:
                    user_msg = _USER_MSG_LLM_THROTTLED
                elif "rate limit" in err_str:
                    user_msg = _USER_MSG_LLM_THROTTLED
                else:
                    user_msg = _USER_MSG_LLM_UNAVAILABLE
                logger.error("LLM streaming failed for chat %s: %s", chat_id, exc)
                yield {"type": "error", "error": user_msg}
                return

            # Step 6: Prepare sources
            sources_data: list[dict[str, Any]] | None = None
            if retrieval_result.sources:
                sources_data = [
                    {
                        "document_id": str(source.document_id),
                        "document_title": source.document_title,
                        "page_number": source.page_number,
                        "chunk_id": str(source.chunk_id),
                        "chunk_index": source.chunk_index,
                        "similarity_score": source.similarity_score,
                        "content_preview": source.content_preview,
                    }
                    for source in retrieval_result.sources
                ]
                yield {"type": "sources", "sources": sources_data}

            # Step 7: Store assistant response
            try:
                message_result = await self.chat_repo.add_message(
                    chat_id=chat_id,
                    sender="assistant",
                    content=accumulated_response,
                    message_index=0,
                    sources=sources_data,
                )
            except (ClientError, EndpointConnectionError) as exc:
                logger.error(
                    "DynamoDB write failed for assistant message in chat %s: %s",
                    chat_id, exc,
                )
                # The user already saw the streamed tokens — log the
                # persistence failure but still emit 'done' so the UI
                # finalises the message bubble.
                yield {"type": "done", "message_id": ""}
                return
            except Exception:
                logger.exception(
                    "Unexpected error storing assistant message in chat %s",
                    chat_id,
                )
                yield {"type": "done", "message_id": ""}
                return

            # Step 8: Send done event
            yield {
                "type": "done",
                "message_id": message_result["message_id"],
            }

        except Exception:
            # Catch-all — should rarely be reached after the granular
            # handling above, but guarantees the stream always ends
            # with a well-formed event.
            logger.exception(
                "Unhandled error in streaming pipeline for chat %s", chat_id,
            )
            yield {"type": "error", "error": _USER_MSG_INTERNAL}
    
    async def process_user_message(
        self,
        chat_id: str,
        project_id: UUID,
        user_message: str,
    ) -> dict[str, Any]:
        """
        Process user message and return complete response (non-streaming).

        This is useful for testing or as a fallback when SSE is not
        available.

        Error handling:
        - DynamoDB write failures → ``ServiceUnavailableError``
        - Bedrock failures → ``ServiceUnavailableError`` (transient) or
          ``RuntimeError`` (permanent).
        - Retrieval / memory failures → graceful degradation, logged.

        Raises:
            ServiceUnavailableError: for transient AWS failures.
            RuntimeError: for permanent / unexpected LLM failures.
        """
        # Step 1: Store user message
        try:
            await self.chat_repo.add_message(
                chat_id=chat_id,
                sender="user",
                content=user_message,
                message_index=0,
            )
        except (ClientError, EndpointConnectionError) as exc:
            logger.error(
                "DynamoDB write failed for user message in chat %s: %s",
                chat_id, exc,
            )
            raise ServiceUnavailableError(_USER_MSG_STORAGE_FAILED) from exc

        # Step 2: Retrieve context (graceful degradation)
        retrieval_result = await self._retrieve_context(project_id, user_message)

        # Step 3: Conversation history (graceful degradation)
        formatted_messages, conversation_summary = await self._get_history(chat_id)

        # Step 4: Build prompt with memory
        prompt = self.prompt_builder.build_prompt(
            user_question=user_message,
            retrieved_context=retrieval_result.context,
            conversation_summary=conversation_summary,
            recent_messages=formatted_messages,
        )

        # Step 5: Generate response
        try:
            response = await self.llm_provider.generate(prompt)
        except ClientError as exc:
            user_msg = _classify_aws_error(exc)
            logger.error(
                "Bedrock generation error in chat %s: %s — %s",
                chat_id, exc.response["Error"]["Code"], exc,
            )
            raise ServiceUnavailableError(user_msg) from exc
        except EndpointConnectionError as exc:
            logger.error(
                "Bedrock endpoint unreachable for chat %s: %s", chat_id, exc,
            )
            raise ServiceUnavailableError(_USER_MSG_LLM_UNAVAILABLE) from exc
        except RuntimeError:
            # Already a well-typed error from BedrockNovaProvider — re-raise
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected LLM error in chat %s", chat_id,
            )
            raise RuntimeError(_USER_MSG_INTERNAL) from exc

        # Step 6: Prepare sources
        sources_data: list[dict[str, Any]] | None = None
        if retrieval_result.sources:
            sources_data = [
                {
                    "document_id": str(source.document_id),
                    "document_title": source.document_title,
                    "page_number": source.page_number,
                    "chunk_id": str(source.chunk_id),
                    "chunk_index": source.chunk_index,
                    "similarity_score": source.similarity_score,
                    "content_preview": source.content_preview,
                }
                for source in retrieval_result.sources
            ]

        # Step 7: Store assistant response
        try:
            message_result = await self.chat_repo.add_message(
                chat_id=chat_id,
                sender="assistant",
                content=response,
                message_index=0,
                sources=sources_data,
            )
        except (ClientError, EndpointConnectionError) as exc:
            logger.error(
                "DynamoDB write failed for assistant message in chat %s: %s",
                chat_id, exc,
            )
            # The generation succeeded — return the content to the caller
            # even though persistence failed, and log the issue.
            return {
                "message_id": "",
                "content": response,
                "sources": sources_data or [],
            }

        return {
            "message_id": message_result["message_id"],
            "content": response,
            "sources": sources_data or [],
        }

    # ------------------------------------------------------------------
    # Internal helpers (shared by streaming & non-streaming paths)
    # ------------------------------------------------------------------

    async def _retrieve_context(
        self, project_id: UUID, user_message: str,
    ) -> RetrievalResult:
        """Retrieve document context, degrading gracefully on failure."""
        empty = RetrievalResult(context="", sources=[], chunk_count=0)

        if self.retrieval_service is None:
            return empty

        try:
            return await self.retrieval_service.retrieve_for_query(
                project_id=project_id,
                query=user_message,
            )
        except ValueError:
            # Project has no documents — expected, not an error
            return empty
        except Exception as exc:
            logger.error(
                "Retrieval failed for project %s: %s", project_id, exc,
            )
            return empty

    async def _get_history(
        self, chat_id: str,
    ) -> tuple[list[dict[str, str]], str | None]:
        """Return ``(formatted_messages, conversation_summary)``.

        Falls back to raw recent messages if conversation memory fails,
        and returns empty history if even that fails.
        """
        try:
            if self.conversation_memory:
                context = await self.conversation_memory.get_context(chat_id)
                formatted = [
                    {"role": msg.role.value, "content": msg.content}
                    for msg in context.recent_messages
                ]
                return formatted, context.summary
        except Exception as exc:
            logger.error(
                "Conversation memory failed for chat %s: %s", chat_id, exc,
            )
            # Fall through to raw history below

        # Fallback: simple recent messages (no summary)
        try:
            recent_messages = await self.chat_repo.get_recent_messages(
                chat_id=chat_id,
                count=10,
            )
            formatted = [
                {"role": msg["sender"], "content": msg["content"]}
                for msg in recent_messages
            ]
            return formatted, None
        except Exception as exc:
            logger.error(
                "Failed to fetch recent messages for chat %s: %s",
                chat_id, exc,
            )
            return [], None

