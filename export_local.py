# -*- coding: utf-8 -*-
"""
editor_pipeline/export.py — Lưu CHỈ final_text ra file .txt
- Không lưu audit.
"""

import os  # thao tác thư mục/đường dẫn
from typing import Optional


def save_final_text_txt(final_text: str, out_path: str, *, encoding: str = "utf-8", ensure_trailing_newline: bool = True) -> str:
    """
    Ghi CHỈ final_text ra một file .txt.

    Args:
        final_text: Chuỗi văn bản sau biên tập (đã ghép từ các chunk).
        out_path : Đường dẫn file .txt cần lưu (vd: './outputs/result.txt').
        encoding : Mã hoá file, mặc định 'utf-8'.
        ensure_trailing_newline: Nếu True, đảm bảo có newline ở cuối file (thân thiện POSIX).

    Returns:
        str: Đường dẫn file vừa ghi (out_path).
    """
    # Tạo thư mục đích nếu cần (nếu out_path có chứa folder)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Nội dung cần ghi
    content: str = final_text or ""
    if ensure_trailing_newline and (not content.endswith("\n")):
        content = content + "\n"

    # Ghi file văn bản
    with open(out_path, "w", encoding=encoding) as f:
        f.write(content)

    return out_path
