"""
Section-aware chunker.

Instead of fixed-size token windows (which shred table rows and break
section boundaries), we:
  1. Group consecutive elements under the same section Title.
  2. Keep tables as atomic chunks — never split a table across chunks.
  3. Merge tiny fragments into their nearest neighbour.
  4. Cap chunks at MAX_CHUNK_WORDS to avoid oversized context windows.

Each chunk carries metadata that the Router Agent uses for targeted
retrieval: section_title, page numbers, element types present.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from backend.ingestion.pdf_parser import ElementType, ParsedElement
from backend.ingestion.table_describer import describe_table
from backend.observability.logger import get_logger

logger = get_logger(__name__)

MAX_CHUNK_WORDS = 400      # soft cap; tables may exceed this
MIN_CHUNK_WORDS = 20       # fragments below this are merged upward


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str                                    # document stored in ChromaDB (HTML for tables)
    section_title: Optional[str]                 # nearest Title ancestor
    page_numbers: List[int] = field(default_factory=list)
    element_types: List[str] = field(default_factory=list)
    contains_table: bool = False
    chunk_index: int = 0
    source_element_indices: List[int] = field(default_factory=list)
    embedding_text: Optional[str] = None         # text to embed; falls back to text if None

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def to_metadata_dict(self) -> dict:
        """Serialise metadata for ChromaDB storage (all values must be str/int/float/bool)."""
        return {
            "chunk_id": self.chunk_id,
            "section_title": self.section_title or "",
            "page_numbers": ",".join(str(p) for p in self.page_numbers),
            "contains_table": self.contains_table,
            "chunk_index": self.chunk_index,
            "element_types": ",".join(self.element_types),
            "word_count": self.word_count,
        }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _build_table_texts(
    element: ParsedElement,
    section_title: Optional[str],
    trace_id: str,
) -> tuple[str, Optional[str]]:
    """
    Return (document_text, embedding_text) for a table chunk.

    document_text  — stored in ChromaDB and returned to agents; HTML when
                     available so no structure is lost.
    embedding_text — passed to the sentence encoder; an LLM-generated prose
                     description so the vector aligns with natural-language
                     queries. None means fall back to document_text.
    """
    if element.html_content:
        description = describe_table(
            html_content=element.html_content,
            section_title=section_title,
            trace_id=trace_id,
        )
        return element.html_content, description  # description may be None on failure

    # No HTML available — plain text for both
    return f"[TABLE] {element.text}", None


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def chunk_elements(
    elements: List[ParsedElement],
    trace_id: str = "unknown",
    max_chunk_words: int = MAX_CHUNK_WORDS,
    min_chunk_words: int = MIN_CHUNK_WORDS,
) -> List[DocumentChunk]:
    """
    Convert a flat list of ParsedElements into DocumentChunks.

    Strategy:
    - Each Title element opens a new section group.
    - Table elements always become their own chunk (atomic).
    - Text elements within a section are accumulated until
      the word count would exceed max_chunk_words, then flushed.
    - Fragments smaller than min_chunk_words are merged into the
      preceding chunk if possible.
    """
    t0 = time.perf_counter()

    if not elements:
        logger.warning("chunk_elements_empty_input", trace_id=trace_id)
        return []

    chunks: List[DocumentChunk] = []
    chunk_index = 0

    # Working buffer for text accumulation within a section
    buffer_texts: List[str] = []
    buffer_pages: List[int] = []
    buffer_types: List[str] = []
    buffer_elem_indices: List[int] = []
    current_section: Optional[str] = None

    def flush_buffer() -> None:
        nonlocal chunk_index
        if not buffer_texts:
            return

        combined = " ".join(buffer_texts)

        # Merge tiny fragments into previous chunk rather than creating stub chunks
        if len(combined.split()) < min_chunk_words and chunks:
            prev = chunks[-1]
            prev.text = prev.text + " " + combined
            prev.page_numbers = sorted(set(prev.page_numbers + buffer_pages))
            prev.element_types = list(set(prev.element_types + buffer_types))
            prev.source_element_indices += buffer_elem_indices
            buffer_texts.clear()
            buffer_pages.clear()
            buffer_types.clear()
            buffer_elem_indices.clear()
            return

        chunks.append(
            DocumentChunk(
                chunk_id=str(uuid.uuid4()),
                text=combined,
                section_title=current_section,
                page_numbers=sorted(set(buffer_pages)),
                element_types=list(set(buffer_types)),
                contains_table=False,
                chunk_index=chunk_index,
                source_element_indices=list(buffer_elem_indices),
            )
        )
        chunk_index += 1
        buffer_texts.clear()
        buffer_pages.clear()
        buffer_types.clear()
        buffer_elem_indices.clear()

    for element in elements:
        pages = [element.page_number] if element.page_number else []

        # ── Title: flush current buffer, open new section ──
        if element.is_title:
            flush_buffer()
            current_section = element.text
            # Add the title text itself to the new buffer so it's in the chunk
            buffer_texts.append(element.text)
            buffer_pages.extend(pages)
            buffer_types.append(element.element_type.value)
            buffer_elem_indices.append(element.element_index)
            continue

        # ── Table: always its own atomic chunk ──
        if element.is_table:
            flush_buffer()
            doc_text, emb_text = _build_table_texts(element, current_section, trace_id)
            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    text=doc_text,
                    embedding_text=emb_text,
                    section_title=current_section,
                    page_numbers=sorted(set(pages)),
                    element_types=[ElementType.TABLE.value],
                    contains_table=True,
                    chunk_index=chunk_index,
                    source_element_indices=[element.element_index],
                )
            )
            chunk_index += 1
            continue

        # ── Text / Narrative / ListItem: accumulate ──
        current_words = sum(len(t.split()) for t in buffer_texts)
        incoming_words = element.word_count

        # Flush if adding this element would breach the cap
        if current_words + incoming_words > max_chunk_words and buffer_texts:
            flush_buffer()

        buffer_texts.append(element.text)
        buffer_pages.extend(pages)
        buffer_types.append(element.element_type.value)
        buffer_elem_indices.append(element.element_index)

    # Flush any remaining buffer
    flush_buffer()

    duration_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "chunking_complete",
        trace_id=trace_id,
        total_chunks=len(chunks),
        table_chunks=sum(1 for c in chunks if c.contains_table),
        text_chunks=sum(1 for c in chunks if not c.contains_table),
        avg_words=round(sum(c.word_count for c in chunks) / max(len(chunks), 1), 1),
        duration_ms=round(duration_ms, 2),
    )

    return chunks
