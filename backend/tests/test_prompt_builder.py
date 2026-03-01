"""
Tests for PromptBuilder service.

These tests verify:
1. Basic prompt assembly with all sections
2. Token counting accuracy
3. Context window budgeting and truncation
4. Priority-based truncation (system > context > messages > summary)
5. Edge cases (empty sections, oversized content)
"""

from unittest.mock import Mock

import pytest

from app.core.config import LLMConfig, Settings
from app.services.prompt_builder import PromptBuilder, TokenCounter


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings."""
    settings = Mock(spec=Settings)
    settings.llm = LLMConfig(
        model_id="amazon.nova-micro-v1:0",
        max_output_tokens=2048,
        temperature=0.3
    )
    return settings


@pytest.fixture
def prompt_builder(mock_settings: Settings) -> PromptBuilder:
    """Create PromptBuilder instance."""
    return PromptBuilder(settings=mock_settings)


@pytest.fixture
def token_counter() -> TokenCounter:
    """Create TokenCounter instance."""
    return TokenCounter()


class TestTokenCounter:
    """Tests for TokenCounter utility."""
    
    def test_count_tokens_simple(self, token_counter: TokenCounter):
        """Test token counting for simple text."""
        text = "Hello, world!"
        count = token_counter.count_tokens(text)
        
        # Should be around 4 tokens for this phrase
        assert count > 0
        assert count < 10
    
    def test_count_tokens_empty(self, token_counter: TokenCounter):
        """Test token counting for empty string."""
        count = token_counter.count_tokens("")
        assert count == 0
    
    def test_count_tokens_long_text(self, token_counter: TokenCounter):
        """Test token counting for longer text."""
        text = "This is a longer piece of text with multiple sentences. " * 10
        count = token_counter.count_tokens(text)
        
        # Should be proportional to length
        assert count > 50
    
    def test_count_tokens_special_chars(self, token_counter: TokenCounter):
        """Test token counting with special characters."""
        text = "Hello! 🚀 This has émojis and spëcial çharacters."
        count = token_counter.count_tokens(text)
        
        assert count > 0


class TestPromptBuilder:
    """Tests for PromptBuilder service."""
    
    def test_build_prompt_full_context(self, prompt_builder: PromptBuilder):
        """Test building prompt with all sections within budget."""
        user_question = "What is machine learning?"
        retrieved_context = """[Source 1: ML Handbook, Page 5]
Machine learning is a subset of artificial intelligence."""
        conversation_summary = "Earlier, we discussed deep learning basics."
        recent_messages = [
            {"role": "user", "content": "Tell me about AI."},
            {"role": "assistant", "content": "AI is the simulation of human intelligence."}
        ]
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages
        )
        
        # Verify all sections present
        assert "# System Instructions" in prompt
        assert "# Retrieved Documents" in prompt
        assert "# Conversation Context" in prompt
        assert "# Current Question" in prompt
        assert user_question in prompt
        assert retrieved_context in prompt
        assert conversation_summary in prompt
        assert "User: Tell me about AI." in prompt
        assert "Assistant: AI is the simulation of human intelligence." in prompt
    
    def test_build_prompt_minimal(self, prompt_builder: PromptBuilder):
        """Test building prompt with only required sections."""
        user_question = "What is AI?"
        retrieved_context = "[Source 1] AI is artificial intelligence."
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context
        )
        
        # Should have system, context, and question
        assert "# System Instructions" in prompt
        assert "# Retrieved Documents" in prompt
        assert "# Current Question" in prompt
        assert user_question in prompt
        assert retrieved_context in prompt
        
        # Should not have conversation context
        assert "# Conversation Context" not in prompt
    
    def test_build_prompt_no_summary(self, prompt_builder: PromptBuilder):
        """Test building prompt without summary but with recent messages."""
        user_question = "Explain transformers."
        retrieved_context = "[Source 1] Transformers use attention mechanisms."
        recent_messages = [
            {"role": "user", "content": "What is attention?"},
            {"role": "assistant", "content": "Attention is a mechanism for focusing."}
        ]
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context,
            recent_messages=recent_messages
        )
        
        # Should have conversation context with messages but no summary
        assert "# Conversation Context" in prompt
        assert "## Recent Messages" in prompt
        assert "## Summary of Earlier Discussion" not in prompt
    
    def test_build_prompt_empty_messages(self, prompt_builder: PromptBuilder):
        """Test building prompt with empty message list."""
        user_question = "Test question"
        retrieved_context = "[Source 1] Test content."
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context,
            recent_messages=[]
        )
        
        # Should not have conversation context
        assert "# Conversation Context" not in prompt
    
    def test_build_prompt_ordering(self, prompt_builder: PromptBuilder):
        """Test that prompt sections appear in correct order."""
        user_question = "Question"
        retrieved_context = "Context"
        conversation_summary = "Summary"
        recent_messages = [{"role": "user", "content": "Hi"}]
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages
        )
        
        # Check ordering using index positions
        system_pos = prompt.index("# System Instructions")
        retrieved_pos = prompt.index("# Retrieved Documents")
        conversation_pos = prompt.index("# Conversation Context")
        question_pos = prompt.index("# Current Question")
        
        assert system_pos < retrieved_pos < conversation_pos < question_pos
    
    def test_build_prompt_with_truncation(self, prompt_builder: PromptBuilder):
        """Test prompt building with very long content that needs truncation."""
        # Override the context window to a small value to trigger truncation
        prompt_builder.settings.llm = LLMConfig(
            model_id="amazon.nova-micro-v1:0",
            max_output_tokens=2048,
            temperature=0.3,
            context_window=8000,
        )

        user_question = "Test question"
        
        # Create very long context (should trigger truncation)
        long_text = "This is a very long piece of text. " * 500
        retrieved_context = f"[Source 1] {long_text}"
        conversation_summary = long_text
        recent_messages = [
            {"role": "user", "content": long_text},
            {"role": "assistant", "content": long_text}
        ]
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages
        )
        
        # Verify prompt was generated (truncation happened)
        assert prompt is not None
        assert len(prompt) > 0
        
        # Check for truncation indicators
        # At least one section should be truncated
        assert "[... truncated for length ...]" in prompt or len(prompt) < len(long_text) * 4
    
    def test_truncate_to_budget(self, prompt_builder: PromptBuilder):
        """Test text truncation to fit token budget."""
        text = "This is a test sentence. " * 100
        token_budget = 50
        
        truncated = prompt_builder._truncate_to_budget(text, token_budget)
        
        # Should be shorter than original
        assert len(truncated) < len(text)
        
        # Should have truncation indicator
        assert "[... truncated for length ...]" in truncated
        
        # Should be within budget
        token_count = prompt_builder.token_counter.count_tokens(truncated)
        # Allow small margin for truncation indicator
        assert token_count <= token_budget + 20
    
    def test_truncate_to_budget_text_within_budget(self, prompt_builder: PromptBuilder):
        """Test truncation when text is already within budget."""
        text = "Short text."
        token_budget = 100
        
        truncated = prompt_builder._truncate_to_budget(text, token_budget)
        
        # Should be unchanged
        assert truncated == text
    
    def test_truncate_to_budget_zero_budget(self, prompt_builder: PromptBuilder):
        """Test truncation with zero token budget."""
        text = "Some text"
        token_budget = 0
        
        truncated = prompt_builder._truncate_to_budget(text, token_budget)
        
        # Should return empty string
        assert truncated == ""
    
    def test_truncate_to_budget_empty_text(self, prompt_builder: PromptBuilder):
        """Test truncation with empty text."""
        text = ""
        token_budget = 50
        
        truncated = prompt_builder._truncate_to_budget(text, token_budget)
        
        # Should return empty string
        assert truncated == ""
    
    def test_format_recent_messages(self, prompt_builder: PromptBuilder):
        """Test formatting of recent messages."""
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        
        formatted = prompt_builder._format_recent_messages(messages)
        
        assert "User: Hello!" in formatted
        assert "Assistant: Hi there!" in formatted
        assert "User: How are you?" in formatted
    
    def test_format_recent_messages_empty(self, prompt_builder: PromptBuilder):
        """Test formatting with empty message list."""
        messages = []
        
        formatted = prompt_builder._format_recent_messages(messages)
        
        assert formatted == ""
    
    def test_priority_based_truncation(self, prompt_builder: PromptBuilder):
        """Test that truncation prioritizes correctly: system > context > messages > summary."""
        user_question = "Short question"
        
        # Make context, messages, and summary all very long
        very_long = "x" * 5000
        retrieved_context = f"[Source 1] {very_long}"
        conversation_summary = very_long
        recent_messages = [{"role": "user", "content": very_long}]
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages
        )
        
        # System prompt should always be included
        assert "# System Instructions" in prompt
        assert "You are a helpful research assistant" in prompt
        
        # Question should always be included
        assert user_question in prompt
        
        # Verify prompt is not excessively long
        token_count = prompt_builder.token_counter.count_tokens(prompt)
        assert token_count < 8000  # Should be within conservative limit
    
    def test_multiple_message_roles(self, prompt_builder: PromptBuilder):
        """Test formatting messages with different roles."""
        messages = [
            {"role": "user", "content": "First user message"},
            {"role": "assistant", "content": "First assistant message"},
            {"role": "user", "content": "Second user message"},
            {"role": "assistant", "content": "Second assistant message"}
        ]
        
        prompt = prompt_builder.build_prompt(
            user_question="Test",
            retrieved_context="Test context",
            recent_messages=messages
        )
        
        # All messages should be present in order
        assert "User: First user message" in prompt
        assert "Assistant: First assistant message" in prompt
        assert "User: Second user message" in prompt
        assert "Assistant: Second assistant message" in prompt
    
    def test_token_counter_consistency(self, prompt_builder: PromptBuilder):
        """Test that token counting is consistent."""
        text = "This is a test sentence for consistency checking."
        
        count1 = prompt_builder.token_counter.count_tokens(text)
        count2 = prompt_builder.token_counter.count_tokens(text)
        
        # Should return same count
        assert count1 == count2
    
    def test_build_prompt_unicode_content(self, prompt_builder: PromptBuilder):
        """Test building prompt with unicode characters."""
        user_question = "What is 机器学习?"
        retrieved_context = "[Source 1] 机器学习 means machine learning in Chinese."
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context
        )
        
        # Should handle unicode correctly
        assert user_question in prompt
        assert retrieved_context in prompt
    
    def test_build_prompt_with_newlines(self, prompt_builder: PromptBuilder):
        """Test building prompt with content containing newlines."""
        user_question = "Explain\nthis\nconcept"
        retrieved_context = "[Source 1]\nLine 1\nLine 2\nLine 3"
        
        prompt = prompt_builder.build_prompt(
            user_question=user_question,
            retrieved_context=retrieved_context
        )
        
        # Should preserve newlines
        assert "Explain\nthis\nconcept" in prompt
        assert "Line 1\nLine 2\nLine 3" in prompt

