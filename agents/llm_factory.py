"""
LLM Factory — helper functions for creating ChatGroq instances with automatic fallback.

Primary model:  config.GROQ_MODEL          (llama-3.3-70b-versatile by default)
Fallback model: config.GROQ_FALLBACK_MODEL (llama-3.1-8b-instant by default)

Groq free tier has SEPARATE daily token quotas per model:
  - llama-3.3-70b-versatile : ~100k tokens/day
  - llama-3.1-8b-instant    : ~500k tokens/day

When the 70B model's quota is exhausted, agents automatically fall back to the 8B model.
"""

from langchain_groq import ChatGroq
import config

# Fallback model name — exported so agents can reference it
FALLBACK_MODEL: str = getattr(config, "GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")


def get_llm(temperature: float = 0.3, streaming: bool = False):
    """
    Return primary LLM with .with_fallbacks([fallback_llm]).
    Use this for chains that end in StrOutputParser (not with_structured_output).
    """
    primary = _build(config.GROQ_MODEL, temperature, streaming)
    fallback = _build(FALLBACK_MODEL, temperature, streaming)
    return primary.with_fallbacks([fallback])


def get_primary_llm(temperature: float = 0.3, streaming: bool = False) -> ChatGroq:
    """Return the primary ChatGroq instance (needed when calling .with_structured_output())."""
    return _build(config.GROQ_MODEL, temperature, streaming)


def get_fallback_llm(temperature: float = 0.3, streaming: bool = False) -> ChatGroq:
    """Return the fallback ChatGroq instance."""
    return _build(FALLBACK_MODEL, temperature, streaming)


def _build(model: str, temperature: float, streaming: bool) -> ChatGroq:
    return ChatGroq(
        model=model,
        temperature=temperature,
        api_key=config.GROQ_API_KEY,
        streaming=streaming,
    )
