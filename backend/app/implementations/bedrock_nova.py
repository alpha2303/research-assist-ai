"""LLM provider implementation using AWS Bedrock Amazon Nova models."""

import asyncio
import json
from typing import Any, AsyncIterator

import boto3
from botocore.exceptions import ClientError

from app.core.config import LLMConfig
from app.core.interfaces.llm_provider import LLMProvider


class BedrockNovaProvider(LLMProvider):
    """
    LLM provider using Amazon Nova models via Bedrock.
    
    Models:
    - Nova Micro (amazon.nova-micro-v1:0): Fastest, cheapest - for dev/testing
    - Nova Lite (amazon.nova-lite-v1:0): Balanced - for production
    - Nova Pro (amazon.nova-pro-v1:0): Best quality - for high-value use cases
    
    Features:
    - Streaming and non-streaming generation
    - Configurable temperature and max tokens
    - Exponential backoff for rate limiting
    - AWS Converse API for unified interface
    """

    def __init__(self, config: LLMConfig, aws_profile: str, aws_region: str):
        """
        Initialize Bedrock Nova provider.
        
        Args:
            config: LLM configuration
            aws_profile: AWS profile name
            aws_region: AWS region
        """
        self.config = config
        
        # Initialize Bedrock runtime client
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        self.bedrock_runtime = session.client("bedrock-runtime")
        
        # Rate limiting configuration
        self.max_retries = 3
        self.initial_retry_delay = 1.0  # seconds

    async def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """
        Generate text completion (non-streaming).
        
        Uses the Bedrock Converse API for unified interface across models.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate (defaults to config value)
            temperature: Sampling temperature (defaults to config value)
            stop_sequences: Sequences that stop generation
            
        Returns:
            Generated text
            
        Raises:
            RuntimeError: If generation fails after retries
        """
        # Use config defaults if not specified
        if max_tokens is None:
            max_tokens = self.config.max_output_tokens
        if temperature is None:
            temperature = self.config.temperature
        
        # Prepare inference configuration
        inference_config: dict[str, Any] = {
            "maxTokens": max_tokens,
            "temperature": temperature,
        }
        
        if stop_sequences:
            inference_config["stopSequences"] = stop_sequences
        
        # Prepare request
        request_body = {
            "modelId": self.config.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": inference_config
        }
        
        # Call Bedrock with retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self.bedrock_runtime.converse,
                    **request_body
                )
                
                # Extract generated text from response
                output = response["output"]
                message = output["message"]
                content = message["content"][0]
                generated_text = content["text"]
                
                return generated_text
                
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                last_error = e
                
                # Handle throttling with exponential backoff
                if error_code == "ThrottlingException" and attempt < self.max_retries - 1:
                    delay = self.initial_retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                elif error_code == "ThrottlingException":
                    # Last retry for throttling - will raise below
                    break
                
                # Re-raise other errors immediately
                raise RuntimeError(
                    f"Bedrock generation failed: {error_code} - {str(e)}"
                ) from e
                
            except Exception as e:
                raise RuntimeError(f"LLM generation failed: {str(e)}") from e
        
        # If we get here, all retries failed with throttling
        if last_error:
            raise RuntimeError("Max retries exceeded for LLM generation") from last_error
        raise RuntimeError("Max retries exceeded for LLM generation")

    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """
        Generate text completion with token streaming.
        
        Uses the Bedrock ConverseStream API for real-time token delivery.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop_sequences: Sequences that stop generation
            
        Yields:
            Generated tokens as they are produced
            
        Raises:
            RuntimeError: If streaming fails
        """
        # Use config defaults if not specified
        if max_tokens is None:
            max_tokens = self.config.max_output_tokens
        if temperature is None:
            temperature = self.config.temperature
        
        # Prepare inference configuration
        inference_config: dict[str, Any] = {
            "maxTokens": max_tokens,
            "temperature": temperature,
        }
        
        if stop_sequences:
            inference_config["stopSequences"] = stop_sequences
        
        # Prepare request
        request_body = {
            "modelId": self.config.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": inference_config
        }
        
        try:
            # Call ConverseStream API in thread pool (boto3 is synchronous)
            response = await asyncio.to_thread(
                self.bedrock_runtime.converse_stream,
                **request_body
            )
            
            # Stream tokens from response
            stream = response.get("stream")
            if stream:
                for event in stream:
                    # contentBlockDelta events contain the actual text chunks
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"]["delta"]
                        if "text" in delta:
                            yield delta["text"]
                    
                    # Check for errors in the stream
                    elif "internalServerException" in event:
                        raise RuntimeError("Internal server error during streaming")
                    elif "modelStreamErrorException" in event:
                        error = event["modelStreamErrorException"]
                        raise RuntimeError(f"Model stream error: {error.get('message', 'Unknown error')}")
                    elif "throttlingException" in event:
                        raise RuntimeError("Rate limit exceeded during streaming")
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            raise RuntimeError(
                f"Bedrock streaming failed: {error_code} - {str(e)}"
            ) from e
            
        except Exception as e:
            raise RuntimeError(f"LLM streaming failed: {str(e)}") from e

    def get_model_id(self) -> str:
        """Get the Nova model identifier."""
        return self.config.model_id

    async def close(self) -> None:
        """Close Bedrock client connections."""
        # Boto3 clients are thread-safe and don't need explicit closing
        # But we implement this for interface compliance
        pass

