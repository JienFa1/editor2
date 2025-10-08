# -*- coding: utf-8 -*-
"""
editor_pipeline/docx_ingest.py — đọc .docx từ đường dẫn trong Config.DOCUMENT
Yêu cầu: python-docx đã có trong requirements.txt
"""

from typing import List
import os
from docx import Document               # đã đảm bảo cài sẵn
import Config                    # lấy biến DOCUMENT (đường dẫn .docx)

def get_document_path() -> str:
    """Lấy & kiểm tra đường dẫn .docx từ Config.DOCUMENT."""
    path = getattr(Config, "DOCUMENT", None)
    if not isinstance(path, str) or not path.strip():
        raise RuntimeError("Config.DOCUMENT phải là đường dẫn .docx (str).")
    path = path.strip()
    if not os.path.isfile(path):
        raise RuntimeError(f"File .docx không tồn tại: {path}")
    return path

def read_paragraphs_from_Config() -> List[str]:
    """Đọc các paragraph theo thứ tự từ file .docx trong Config.DOCUMENT."""
    path = get_document_path()
    doc = Document(path)
    return [(p.text or "").strip() for p in doc.paragraphs]

def paragraphs_to_big_text(paragraphs: List[str]) -> str:
    """Ghép danh sách paragraph thành big_text (ngăn bằng 2 newline)."""
    cleaned = [p.strip() for p in paragraphs if isinstance(p, str)]
    return "\n\n".join(cleaned)

def document_to_big_text() -> str:
    """Đọc trực tiếp từ DOCUMENT và trả về big_text."""
    return paragraphs_to_big_text(read_paragraphs_from_Config())
