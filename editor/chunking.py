# -*- coding: utf-8 -*-
"""
editor_pipeline/chunking.py — CẮT THEO ĐOẠN (paragraph-only)

Yêu cầu mới: mỗi **đoạn** (paragraph) trong big_text → 1 Chunk.
- Không cắt mềm theo câu.
- Không gộp đoạn ngắn.
- Không chia nhỏ đoạn dài.
Giữ nguyên chữ ký hàm để không ảnh hưởng module khác (max_chars, min_merge bị bỏ qua).
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Chunk:
    """Đại diện một đoạn văn đã cắt để gửi cho LLM chỉnh sửa."""
    chunk_id: str        # "C1", "C2", ...
    order: int           # 1-based theo thứ tự xuất hiện
    text: str            # nội dung của đoạn
    start_par: int = -1  # index paragraph bắt đầu (0-based); bằng end_par vì 1 đoạn = 1 paragraph
    end_par: int = -1    # index paragraph kết thúc (0-based)


def split_text(big_text: str, max_chars: int = 0, min_merge: int = 0) -> List[Chunk]:
    """
    Cắt theo đoạn (paragraph-only):
      - Mỗi khối được ngăn cách bởi HAI newline '\\n\\n' được coi là 1 đoạn.
      - Bỏ qua tham số max_chars, min_merge (giữ để tương thích hàm gọi).

    Args:
        big_text: Chuỗi văn bản lớn đã ghép từ .docx (paragraphs_to_big_text).
        max_chars: (bị bỏ qua)
        min_merge: (bị bỏ qua)

    Returns:
        List[Chunk]: danh sách Chunk theo đúng thứ tự đoạn.
    """
    # Chuẩn hoá newline
    text = (big_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    # Tách theo ranh giới đoạn (hai newline)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Mỗi paragraph → 1 Chunk, gán index 0-based vào start_par/end_par
    chunks: List[Chunk] = []
    for i, para in enumerate(paragraphs):
        chunks.append(
            Chunk(
                chunk_id=f"C{i+1}",
                order=i + 1,
                text=para,
                start_par=i,
                end_par=i,
            )
        )
    return chunks
