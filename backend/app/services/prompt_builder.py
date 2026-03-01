"""
Prompt builder service for assembling LLM prompts with context window budgeting.

This service assembles complete prompts from:
- System instructions
- Retrieved document chunks
- Conversation history (summary + recent messages)
- Current user question

Token budgeting prioritizes:
1. System prompt (always included)
2. Retrieved chunks (most important for RAG)
3. Recent messages (for conversation continuity)
4. Summary (can be truncated if needed)
"""

import tiktoken
from typing import Any

from app.core.config import Settings
from app.services.prompts import get_rag_system_prompt


class TokenCounter:
    """
    Utility for counting tokens in text.
    
    Uses tiktoken with cl100k_base encoding (used by GPT-4 and similar models).
    This provides a reasonable approximation for Bedrock models like Nova.
    """
    
    def __init__(self):
        """Initialize token counter with cl100k_base encoding."""
        # cl100k_base is used by GPT-4, Claude, and similar modern LLMs
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))


class PromptBuilder:
    """
    Service for assembling LLM prompts with token budgeting.
    
    Ensures prompts stay within the model's context window by:
    1. Calculating token usage across all sections
    2. Prioritizing critical content
    3. Truncating less important sections if needed
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize prompt builder.
        
        Args:
            settings: Application settings (for token limits)
        """
        self.settings = settings
        self.token_counter = TokenCounter()
        
        # Reserve tokens for output and safety margin
        self.max_output_tokens = settings.llm.max_output_tokens
        self.safety_margin = 100  # Extra buffer to avoid edge cases
        
    def build_prompt(
        self,
        user_question: str,
        retrieved_context: str,
        conversation_summary: str | None = None,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Build a complete prompt with token budgeting.
        
        Args:
            user_question: Current user question
            retrieved_context: Retrieved document chunks (formatted)
            conversation_summary: Summary of older messages
            recent_messages: Recent messages [{"role": "user"|"assistant", "content": "..."}]
            
        Returns:
            Assembled prompt string ready for LLM
        """
        # Get system prompt (always included)
        system_prompt = get_rag_system_prompt()
        
        # Calculate available tokens for context
        context_window = self.settings.llm.context_window
        available_tokens = context_window - self.max_output_tokens - self.safety_margin
        
        # Count tokens for each section
        system_tokens = self.token_counter.count_tokens(system_prompt)
        question_tokens = self.token_counter.count_tokens(user_question)
        context_tokens = self.token_counter.count_tokens(retrieved_context)
        
        # Calculate conversation history tokens
        summary_tokens = 0
        if conversation_summary:
            summary_tokens = self.token_counter.count_tokens(conversation_summary)
        
        recent_messages_text = self._format_recent_messages(recent_messages or [])
        messages_tokens = self.token_counter.count_tokens(recent_messages_text)
        
        # Calculate total needed tokens
        total_needed = (
            system_tokens +
            question_tokens +
            context_tokens +
            summary_tokens +
            messages_tokens
        )
        
        # If within budget, assemble full prompt
        if total_needed <= available_tokens:
            return self._assemble_prompt(
                system_prompt=system_prompt,
                retrieved_context=retrieved_context,
                conversation_summary=conversation_summary,
                recent_messages_text=recent_messages_text,
                user_question=user_question
            )
        
        # Otherwise, apply truncation strategy
        # Priority: system > question > context > messages > summary
        tokens_used = system_tokens + question_tokens
        budget_remaining = available_tokens - tokens_used
        
        # Allocate tokens (60% context, 30% messages, 10% summary)
        context_budget = int(budget_remaining * 0.6)
        messages_budget = int(budget_remaining * 0.3)
        summary_budget = budget_remaining - context_budget - messages_budget
        
        # Truncate each section if needed
        truncated_context = self._truncate_to_budget(
            retrieved_context,
            context_budget
        )
        
        truncated_messages = self._truncate_to_budget(
            recent_messages_text,
            messages_budget
        )
        
        truncated_summary = self._truncate_to_budget(
            conversation_summary or "",
            summary_budget
        )
        
        return self._assemble_prompt(
            system_prompt=system_prompt,
            retrieved_context=truncated_context,
            conversation_summary=truncated_summary if truncated_summary else None,
            recent_messages_text=truncated_messages,
            user_question=user_question
        )
    
    def _assemble_prompt(
        self,
        system_prompt: str,
        retrieved_context: str,
        conversation_summary: str | None,
        recent_messages_text: str,
        user_question: str
    ) -> str:
        """
        Assemble the final prompt from all sections.
        
        Args:
            system_prompt: System instructions
            retrieved_context: Retrieved document chunks
            conversation_summary: Summary of older messages
            recent_messages_text: Recent conversation messages
            user_question: Current user question
            
        Returns:
            Assembled prompt
        """
        sections = []
        
        # System prompt
        sections.append(f"# System Instructions\n\n{system_prompt}")
        
        # Retrieved context
        if retrieved_context:
            sections.append(f"# Retrieved Documents\n\n{retrieved_context}")
        
        # Conversation context
        if conversation_summary or recent_messages_text:
            sections.append("# Conversation Context")
            
            if conversation_summary:
                sections.append(f"## Summary of Earlier Discussion\n\n{conversation_summary}")
            
            if recent_messages_text:
                sections.append(f"## Recent Messages\n\n{recent_messages_text}")
        
        # Current question
        sections.append(f"# Current Question\n\n{user_question}")
        
        return "\n\n".join(sections)
    
    def _format_recent_messages(self, messages: list[dict[str, Any]]) -> str:
        """
        Format recent messages for the prompt.
        
        Args:
            messages: List of message dicts with "role" and "content"
            
        Returns:
            Formatted messages text
        """
        if not messages:
            return ""
        
        formatted = []
        for msg in messages:
            role = msg["role"].capitalize()
            content = msg["content"]
            formatted.append(f"{role}: {content}")
        
        return "\n\n".join(formatted)
    
    def _truncate_to_budget(self, text: str, token_budget: int) -> str:
        """
        Truncate text to fit within token budget.
        
        Uses a simple strategy: decode the first N tokens.
        
        Args:
            text: Text to truncate
            token_budget: Maximum tokens allowed
            
        Returns:
            Truncated text
        """
        if not text or token_budget <= 0:
            return ""
        
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= token_budget:
            return text
        
        # Truncate and decode
        truncated_tokens = tokens[:token_budget]
        truncated_text = self.encoding.decode(truncated_tokens)
        
        # Add truncation indicator
        return truncated_text + "\n\n[... truncated for length ...]"
    
    @property
    def encoding(self):
        """Get the tiktoken encoding."""
        return self.token_counter.encoding

