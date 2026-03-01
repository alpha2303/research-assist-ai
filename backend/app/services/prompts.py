"""
System prompts for LLM interactions.

This module contains prompt templates used throughout the application
for different LLM tasks.
"""

# RAG System Prompt for Q&A
RAG_SYSTEM_PROMPT = """You are a helpful research assistant helping users understand academic papers and research documents.

Your task is to answer questions based ONLY on the provided document excerpts. Follow these guidelines:

1. **Stay grounded in the context**: Only use information from the provided source documents. Do not use external knowledge or make assumptions.

2. **Cite your sources**: When you reference information, mention which source it comes from (e.g., "According to Document X, Page Y...").

3. **Be precise**: If the context contains specific numbers, metrics, or technical details, cite them accurately.

4. **Admit uncertainty**: If the answer cannot be found in the provided context, clearly state "I don't have enough information in the provided documents to answer this question."

5. **Synthesize when helpful**: If information from multiple sources is relevant, synthesize them coherently while maintaining source attribution.

6. **Handle follow-ups**: Consider the conversation history when answering, but always prioritize the provided context over previous exchanges.

7. **Format clearly**: Use proper formatting (lists, paragraphs) to make your answer easy to read.

Remember: Your goal is to help users understand research content, not to provide general knowledge. Stay faithful to the source material."""


# Conversation Summarization Prompt
CONVERSATION_SUMMARY_PROMPT = """Summarize the following conversation between a user and an AI assistant about research papers.

Focus on:
- Key questions asked by the user
- Main topics and documents discussed
- Important findings or conclusions mentioned

Keep the summary concise (2-3 sentences) and factual. This summary will be used to maintain context in a long conversation.

Previous Summary (if any):
{previous_summary}

Messages to Summarize:
{messages}

Summary:"""


# System prompt for different tasks
def get_rag_system_prompt() -> str:
    """
    Get the system prompt for RAG-based Q&A.
    
    Returns:
        System prompt text
    """
    return RAG_SYSTEM_PROMPT


def get_conversation_summary_prompt() -> str:
    """
    Get theraw prompt template for conversation summarization.
    
    Returns:
        Summary prompt text
    """
    return """Summarize the following conversation between a user and an AI assistant about research papers.

Focus on:
- Key questions asked by the user
- Main topics and documents discussed
- Important findings or conclusions mentioned

Keep the summary concise (2-3 sentences) and factual. This summary will be used to maintain context in a long conversation."""


def get_summarization_prompt(previous_summary: str, messages: str) -> str:
    """
    Get the prompt for conversation summarization.
    
    Args:
        previous_summary: Previous conversation summary (if any)
        messages: Messages to summarize
        
    Returns:
        Formatted summarization prompt
    """
    if not previous_summary:
        previous_summary = "None"
    
    return CONVERSATION_SUMMARY_PROMPT.format(
        previous_summary=previous_summary,
        messages=messages
    )

