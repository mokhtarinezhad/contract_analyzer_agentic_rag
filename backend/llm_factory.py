"""
LLM factory — returns the right LangChain chat model for a given model name.

Supports Anthropic (claude-*) and OpenAI (gpt-*) models.
All agents call get_llm() instead of instantiating ChatAnthropic directly,
so swapping providers requires only a different model name string.
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from backend.config import settings

# ── Model catalogues ──────────────────────────────────────────────────────────

ANTHROPIC_MODELS: dict[str, str] = {
    "claude-opus-4-7":           "Anthropic — Claude Opus 4.7  (Most Capable)",
    "claude-sonnet-4-6":         "Anthropic — Claude Sonnet 4.6  (Balanced)",
    "claude-haiku-4-5-20251001": "Anthropic — Claude Haiku 4.5  (Fastest)",
}

OPENAI_MODELS: dict[str, str] = {
    "gpt-4o":      "OpenAI — GPT-4o  (Most Capable)",
    "gpt-4o-mini": "OpenAI — GPT-4o Mini  (Balanced)",
    "gpt-4-turbo": "OpenAI — GPT-4 Turbo  (Advanced)",
}

ALL_MODELS: dict[str, str] = {**ANTHROPIC_MODELS, **OPENAI_MODELS}

DEFAULT_MODEL = "claude-sonnet-4-6"


def is_openai_model(model_name: str) -> bool:
    return model_name in OPENAI_MODELS or model_name.startswith("gpt-")


def get_llm(model_name: str | None = None, max_tokens: int = 1024):
    """Return a LangChain chat model for the given model name."""
    name = model_name or settings.llm_model
    if is_openai_model(name):
        return ChatOpenAI(
            model=name,
            max_tokens=max_tokens,
            api_key=settings.openai_api_key or None,
        )
    return ChatAnthropic(
        model=name,
        max_tokens=max_tokens,
        api_key=settings.anthropic_api_key,
    )
