"""
PDF parsing using unstructured.io.

Extracts text, tables, and image-embedded text from PDFs.
Returns a list of ParsedElement objects with rich metadata
(element type, section hierarchy, page number) that drive
section-aware chunking downstream.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from backend.config import settings
from backend.observability.logger import get_logger

logger = get_logger(__name__)


class ElementType(str, Enum):
    TITLE = "Title"
    NARRATIVE = "NarrativeText"
    LIST_ITEM = "ListItem"
    TABLE = "Table"
    IMAGE = "Image"
    HEADER = "Header"
    FOOTER = "Footer"
    FIGURE_CAPTION = "FigureCaption"
    TEXT = "Text"
    UNKNOWN = "Unknown"


@dataclass
class ParsedElement:
    element_type: ElementType
    text: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None   # nearest Title ancestor
    element_index: int = 0                 # position in document
    html_content: Optional[str] = None    # raw HTML for tables
    coordinates: Optional[dict] = None    # bounding box if available
    metadata: dict = field(default_factory=dict)

    @property
    def is_table(self) -> bool:
        return self.element_type == ElementType.TABLE

    @property
    def is_title(self) -> bool:
        return self.element_type == ElementType.TITLE

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def to_chunk_text(self) -> str:
        """Return text suitable for embedding and retrieval."""
        if self.is_table and self.html_content:
            return f"[TABLE] {self.text}"
        if self.section_title:
            return f"[{self.section_title}] {self.text}"
        return self.text


# ─────────────────────────────────────────────
# Element type mapping
# ─────────────────────────────────────────────

_UNSTRUCTURED_TYPE_MAP = {
    "Title": ElementType.TITLE,
    "NarrativeText": ElementType.NARRATIVE,
    "ListItem": ElementType.LIST_ITEM,
    "Table": ElementType.TABLE,
    "Image": ElementType.IMAGE,
    "Header": ElementType.HEADER,
    "Footer": ElementType.FOOTER,
    "FigureCaption": ElementType.FIGURE_CAPTION,
    "Text": ElementType.TEXT,
}


def _map_element_type(cls_name: str) -> ElementType:
    return _UNSTRUCTURED_TYPE_MAP.get(cls_name, ElementType.UNKNOWN)


# ─────────────────────────────────────────────
# Core parser
# ─────────────────────────────────────────────

def parse_pdf(
    file_path: str | Path,
    trace_id: str = "unknown",
    strategy: str | None = None,
    include_ocr: bool = False,
) -> List[ParsedElement]:
    """
    Parse a PDF file using unstructured.io and return structured elements.

    Args:
        file_path:    Path to the PDF file.
        trace_id:     Request trace ID for logging correlation.
        strategy:     unstructured strategy — "fast" for born-digital PDFs,
                      "hi_res" for scanned docs (requires heavier deps).
        include_ocr:  If True, extract text from embedded images via OCR.

    Returns:
        List of ParsedElement objects ordered by document position.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    logger.info(
        "pdf_parse_start",
        trace_id=trace_id,
        filename=file_path.name,
        strategy=strategy,
        file_size_bytes=file_path.stat().st_size,
    )

    t0 = time.perf_counter()

    strategy = strategy or settings.pdf_parse_strategy

    try:
        from unstructured.partition.pdf import partition_pdf  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "unstructured[pdf] is required. Run: pip install 'unstructured[pdf]'"
        ) from exc

    partition_kwargs: dict = {
        "filename": str(file_path),
        "strategy": strategy,
        "include_page_breaks": False,
    }

    if include_ocr or settings.pdf_ocr_enabled:
        partition_kwargs["ocr_languages"] = settings.pdf_ocr_language

    raw_elements = partition_pdf(**partition_kwargs)

    parsed = _convert_elements(raw_elements, trace_id=trace_id)

    duration_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "pdf_parse_complete",
        trace_id=trace_id,
        filename=file_path.name,
        total_elements=len(parsed),
        title_count=sum(1 for e in parsed if e.is_title),
        table_count=sum(1 for e in parsed if e.is_table),
        duration_ms=round(duration_ms, 2),
    )

    return parsed


def _convert_elements(raw_elements: list, trace_id: str) -> List[ParsedElement]:
    """Convert unstructured elements into ParsedElement objects with section context."""
    parsed: List[ParsedElement] = []
    current_section_title: Optional[str] = None

    for idx, element in enumerate(raw_elements):
        cls_name = type(element).__name__
        elem_type = _map_element_type(cls_name)
        text = str(element).strip()

        if not text:
            continue

        # Track the most recent Title to propagate section context
        if elem_type == ElementType.TITLE:
            current_section_title = text

        # Extract metadata safely
        meta = element.metadata if hasattr(element, "metadata") else None
        page_num: Optional[int] = None
        html_content: Optional[str] = None
        coords: Optional[dict] = None

        if meta is not None:
            page_num = getattr(meta, "page_number", None)
            html_content = getattr(meta, "text_as_html", None)

            if hasattr(meta, "coordinates") and meta.coordinates is not None:
                try:
                    coords = {
                        "points": meta.coordinates.points,
                        "system": meta.coordinates.system,
                    }
                except Exception:
                    coords = None

        parsed.append(
            ParsedElement(
                element_type=elem_type,
                text=text,
                page_number=page_num,
                section_title=current_section_title if elem_type != ElementType.TITLE else None,
                element_index=idx,
                html_content=html_content,
                coordinates=coords,
                metadata={
                    "raw_type": cls_name,
                    "trace_id": trace_id,
                },
            )
        )

    return parsed


# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────

def get_document_stats(elements: List[ParsedElement]) -> dict:
    """Return a summary dict for logging / UI display."""
    return {
        "total_elements": len(elements),
        "titles": sum(1 for e in elements if e.is_title),
        "tables": sum(1 for e in elements if e.is_table),
        "narrative_blocks": sum(
            1 for e in elements if e.element_type == ElementType.NARRATIVE
        ),
        "list_items": sum(
            1 for e in elements if e.element_type == ElementType.LIST_ITEM
        ),
        "pages": max((e.page_number or 0 for e in elements), default=0),
        "total_words": sum(e.word_count for e in elements),
    }
