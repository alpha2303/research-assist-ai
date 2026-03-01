"""
LLMProvider interface for large language model interactions.

This interface abstracts LLM operations to allow swapping providers
(e.g., Amazon Nova → Claude → GPT) without changing business logic.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    """
    Abstract interface for LLM text generation.
    
    Implementations:
    - NovaLLMProvider: Amazon Nova (Micro/Lite/Pro) via Bedrock
    - ClaudeLLMProvider: Anthropic Claude via Bedrock (future)
    - GPTLLMProvider: OpenAI GPT-4 (future)
    """
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """
        Generate text completion (non-streaming).
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate (None = use default)
            temperature: Sampling temperature (None = use default)
            stop_sequences: Sequences that stop generation
            
        Returns:
            Generated text
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """
        Generate text completion with token streaming.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop_sequences: Sequences that stop generation
            
        Yields:
            Generated tokens as they are produced
        """
        pass
    
    @abstractmethod
    def get_model_id(self) -> str:
        """
        Get the identifier of the LLM model being used.
        
        Returns:
            Model identifier (e.g., "amazon.nova-micro-v1:0")
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close any open connections and cleanup resources"""
        pass
