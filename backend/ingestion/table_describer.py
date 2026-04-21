"""
LLM-based table description for richer embeddings.

all-MiniLM-L6-v2 is a sentence encoder trained on natural language.
Linearised table dumps (cells concatenated, structure lost) sit far from
natural-language queries in vector space even when the table is the
exact answer.  This module converts HTML tables into concise prose
descriptions so the embedding vector aligns with how analysts phrase
compliance queries.

The description is generated once at ingestion time.
On any failure the caller receives None and falls back to plain text.
"""

from __future__ import annotations

from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import settings
from backend.observability.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a document analyst reviewing a contract or compliance document. "
    "Given an HTML table, write a concise natural language description (2-4 sentences) that:\n"
    "- States what the table tracks or defines\n"
    "- Explains the meaning of each column\n"
    "- Summarises the key rules, values, or requirements encoded in the rows\n"
    "- Uses plain English with no HTML or markdown\n\n"
    "Return only the description text, nothing else."
)


def describe_table(
    html_content: str,
    section_title: Optional[str] = None,
    trace_id: str = "unknown",
) -> Optional[str]:
    """
    Generate a natural language description of a table from its HTML.

    Returns the description string, or None if the LLM call fails so the
    caller can fall back to plain text without raising.
    """
    if not html_content or not html_content.strip():
        return None

    context = f"Section: {section_title}\n\n" if section_title else ""
    user_message = f"{context}HTML table:\n{html_content}"

    try:
        llm = ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            max_tokens=300,
            temperature=0,
        )
        response = llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        )
        description = response.content.strip() if hasattr(response, "content") else ""
        if not description:
            logger.warning(
                "table_description_empty_response",
                trace_id=trace_id,
                section_title=section_title,
            )
            return None

        logger.info(
            "table_description_generated",
            trace_id=trace_id,
            section_title=section_title,
            description_words=len(description.split()),
        )
        return description

    except Exception as exc:
        logger.warning(
            "table_description_failed",
            trace_id=trace_id,
            section_title=section_title,
            error=str(exc),
        )
        return None
