# -*- coding: utf-8 -*-
"""
Helper functions to persist pipeline outputs (text or DOCX).
"""

import os
from typing import Mapping

from docx import Document


def _ensure_parent_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def save_final_text_txt(
    final_text: str,
    out_path: str,
    *,
    encoding: str = "utf-8",
    ensure_trailing_newline: bool = True,
) -> str:
    """
    Write final_text into a plain-text file.
    """
    _ensure_parent_dir(out_path)
    content: str = final_text or ""
    if ensure_trailing_newline and (not content.endswith("\n")):
        content = content + "\n"
    with open(out_path, "w", encoding=encoding) as handle:
        handle.write(content)
    return out_path


def save_document_with_edits(
    document: Document,
    paragraph_updates: Mapping[int, str],
    out_path: str,
) -> str:
    """
    Save a DOCX file after updating paragraph text while keeping images/layout.

    Args:
        document: python-docx Document already loaded (images/styles are intact).
        paragraph_updates: mapping docx paragraph index -> new text.
        out_path: destination DOCX path.
    """
    if not isinstance(paragraph_updates, Mapping):
        raise TypeError("paragraph_updates must be a mapping from paragraph index to text.")

    for idx, new_text in paragraph_updates.items():
        if not isinstance(idx, int):
            raise TypeError("Paragraph index must be an integer.")
        if idx < 0 or idx >= len(document.paragraphs):
            raise ValueError(f"Paragraph index out of range: {idx}")
        paragraph = document.paragraphs[idx]
        paragraph.text = (new_text or "").strip()

    _ensure_parent_dir(out_path)
    document.save(out_path)
    return out_path
