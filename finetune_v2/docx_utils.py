# -*- coding: utf-8 -*-
"""
Helpers to project edited text back into the original DOCX structure.
"""

from __future__ import annotations

from typing import Dict, List

from editor.docx_load import ParagraphRecord
from editor.pipeline import ChunkResult


def _split_edited_text(text: str, count: int) -> List[str]:
    """
    Split edited text into `count` pieces based on double-newline separators.
    """
    normalized = (text or "").strip()
    if count <= 1:
        return [normalized]

    parts = [segment.strip() for segment in normalized.split("\n\n")]
    if not any(parts):
        return [""] * count

    if len(parts) < count:
        parts.extend([""] * (count - len(parts)))
    elif len(parts) > count:
        head = parts[: count - 1]
        tail = "\n\n".join(parts[count - 1 :]).strip()
        parts = head + [tail]
    return parts


def build_paragraph_updates(
    results: List[ChunkResult],
    paragraphs: List[ParagraphRecord],
) -> Dict[int, str]:
    """
    Convert pipeline results into DOCX paragraph updates.

    Returns:
        Mapping from docx paragraph index to the new text content.
    """
    updates: Dict[int, str] = {}
    for result in results:
        indices = result.paragraph_indices or []
        if not indices:
            continue

        split_texts = _split_edited_text(result.edited_text, len(indices))

        for local_idx, new_text in zip(indices, split_texts):
            if local_idx < 0 or local_idx >= len(paragraphs):
                raise IndexError(f"Paragraph index {local_idx} is out of range for the loaded document.")
            docx_index = paragraphs[local_idx].docx_index
            updates[docx_index] = new_text
    return updates
