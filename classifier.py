# -*- coding: utf-8 -*-
"""
editor_pipeline/utils.py — tiện ích cho bước gán nhãn (classifier)

Yêu cầu: KHÔNG nhận allowed_labels từ bên ngoài.
- Luôn dùng đúng config.Config.ALLOWED_LABELS_DEFAULT.
- Ép LLM chỉ trả JSON array các nhãn hợp lệ.
- Parse đầu ra an toàn, lọc theo whitelist và khử trùng lặp.
"""

import json
from typing import List, Tuple

import Config  # danh sách nhãn hợp lệ duy nhất


def build_classifier_prompt() -> Tuple[str, str]:
    """
    Tạo (system, user) prompt cho LLM phân loại nhãn.
    - Dùng Config.ALLOWED_LABELS_DEFAULT 
    - Yêu cầu LLM CHỈ trả về JSON array: ["label1","label2",...]
    """
    labels = Config.ALLOWED_LABELS_DEFAULT
    labels_list_str = "\n".join(f"- {k}" for k in labels)

    system = (
        "Bạn là bộ phân loại nhãn văn bản. "
        "Đọc đoạn văn TIẾNG VIỆT và CHỈ trả về một JSON array các khóa nhãn "
        "nằm trong danh sách cho phép. KHÔNG giải thích, KHÔNG thêm trường khác."
    )

    user = (
        "Danh sách nhãn cho phép (chọn 1 hoặc nhiều):\n"
        f"{labels_list_str}\n\n"
        "Yêu cầu đầu ra: chỉ một JSON array, ví dụ: "
        "[\"thong_bao_muc_vu_gioi_thieu\",\"gioi_thieu_nhan_su\"]\n"
        "KHÔNG kèm lời giải thích.\n\n"
        "Đoạn văn cần phân loại:\n"
        "{{TEXT}}"
    )
    return system, user


def parse_labels_json(model_output: str) -> List[str]:
    """
    Parse chuỗi output của LLM thành List[str] nhãn hợp lệ.
    - Chỉ dùng whitelist = Config.ALLOWED_LABELS_DEFAULT.
    - Ưu tiên json.loads trực tiếp; fallback cắt giữa '[' ... ']'.
    - Khử trùng lặp, giữ thứ tự xuất hiện.
    """
    whitelist = Config.ALLOWED_LABELS_DEFAULT

    def _filter_dedupe(items: List[str]) -> List[str]:
        seen, out = set(), []
        for x in items:
            if isinstance(x, str) and x in whitelist and x not in seen:
                seen.add(x)
                out.append(x)
        return out

    # 1) Parse trực tiếp toàn chuỗi
    try:
        data = json.loads(model_output)
        if isinstance(data, list):
            return _filter_dedupe(data)
    except Exception:
        pass

    # 2) Fallback: tìm JSON array trong chuỗi
    try:
        start = model_output.find("[")
        end = model_output.rfind("]")
        if start >= 0 and end > start:
            data = json.loads(model_output[start : end + 1])
            if isinstance(data, list):
                return _filter_dedupe(data)
    except Exception:
        pass

    # 3) Không parse được → trả rỗng
    return []
