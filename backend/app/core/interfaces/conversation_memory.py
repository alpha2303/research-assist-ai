"""
ConversationMemory interface for managing chat conversation history.

This interface abstracts conversation memory management to allow
different strategies (sliding window, summarization, etc.) without
changing the chat service logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MessageRole(Enum):
    """Role of a message in the conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """A single message in a conversation"""
    role: MessageRole
    content: str
    timestamp: datetime
    message_id: str | None = None
    token_count: int | None = None
    sources: list[dict] | None = None
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = []


@dataclass
class ConversationContext:
    """
    Context needed for LLM prompt construction.
    
    Includes:
    - Running summary of older messages
    - Recent full messages within the sliding window
    """
    summary: str | None
    recent_messages: list[Message]
    summary_through_index: int  # Index of last message included in summary
    
    def format_for_prompt(self) -> str:
        """Format context as text for LLM prompt"""
        parts = []
        
        if self.summary:
            parts.append(f"## Conversation Summary\n{self.summary}\n")
        
        if self.recent_messages:
            parts.append("## Recent Messages")
            for msg in self.recent_messages:
                role_str = msg.role.value.capitalize()
                parts.append(f"{role_str}: {msg.content}")
        
        return "\n\n".join(parts)


class ConversationMemory(ABC):
    """
    Abstract interface for conversation memory management.
    
    Implements sliding window with batch-folded summarization:
    - Last N messages kept in full
    - Older messages batch-summarized and folded into running summary
    
    Implementations:
    - DynamoDBConversationMemory: Uses DynamoDB for storage with Nova Micro for summarization
    """
    
    @abstractmethod
    async def add_message(
        self,
        chat_id: str,
        role: MessageRole,
        content: str,
        sources: list[dict] | None = None,
    ) -> Message:
        """
        Add a new message to the conversation.
        
        Args:
            chat_id: ID of the chat session
            role: Role of the message sender
            content: Message content
            sources: Source documents/citations (for assistant messages)
            
        Returns:
            The created Message object
        """
        pass
    
    @abstractmethod
    async def get_context(
        self,
        chat_id: str,
        window_size: int = 10,
    ) -> ConversationContext:
        """
        Get conversation context for LLM prompt.
        
        Returns:
        - Running summary of older messages
        - Last N full messages (within sliding window)
        
        Args:
            chat_id: ID of the chat session
            window_size: Number of recent messages to include in full
            
        Returns:
            ConversationContext with summary + recent messages
        """
        pass
    
    @abstractmethod
    async def trigger_summarization(
        self,
        chat_id: str,
        batch_size: int = 5,
    ) -> str | None:
        """
        Trigger batch summarization of old messages.
        
        Called when messages fall off the sliding window.
        Summarizes batch_size messages and updates running summary.
        
        Args:
            chat_id: ID of the chat session
            batch_size: Number of messages to fold into summary
            
        Returns:
            Updated summary text, or None if no summarization needed
        """
        pass
    
    @abstractmethod
    async def get_message_count(self, chat_id: str) -> int:
        """
        Get total number of messages in a conversation.
        
        Args:
            chat_id: ID of the chat session
            
        Returns:
            Number of messages
        """
        pass
    
    @abstractmethod
    async def clear_conversation(self, chat_id: str) -> None:
        """
        Clear all messages and summary for a conversation.
        
        Args:
            chat_id: ID of the chat session to clear
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close any open connections and cleanup resources"""
        pass
