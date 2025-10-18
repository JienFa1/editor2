# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
"""
editor_pipeline/utils.py — tiện ích cho bước gán nhãn (classifier)

Yêu cầu: KHÔNG nhận allowed_labels từ bên ngoài.
- Luôn dùng đúng config.Config.ALLOWED_LABELS_DEFAULT.
- Ép LLM chỉ trả JSON array các nhãn hợp lệ.
- Parse đầu ra an toàn, lọc theo whitelist và khử trùng lặp.
"""

import json
import unicodedata
from typing import List, Tuple

from . import Config  # danh sách nhãn hợp lệ duy nhất


def _normalize_label(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFC", value).strip()


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
        "Đọc đoạn văn TIẾNG VIỆT và CHỈ trả về một JSON array các khóa nhãn nằm trong danh sách cho phép."
        "Chỉ trả về các nhãn trong danh sách"
        "KHÔNG giải thích, Không thêm bất kỳ nhãn nào ngoài danh sách."
    )

    user = (
        "Danh sách nhãn cho phép (chọn 1 hoặc nhiều):\n"
        f"{labels_list_str}\n\n"
        "Yêu cầu đầu ra: \n"
        "Chỉ một JSON array\n" 
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
    whitelist_raw = getattr(Config, "ALLOWED_LABELS_DEFAULT", [])
    whitelist_map = {_normalize_label(name): name for name in whitelist_raw}
    key_to_name = getattr(Config, "LABEL_KEY_TO_NAME", {})

    def _filter_dedupe(items: List[str]) -> List[str]:
        seen, out = set(), []
        for candidate in items:
            if not isinstance(candidate, str):
                continue
            norm = _normalize_label(candidate)
            canonical = whitelist_map.get(norm) or key_to_name.get(norm, "")
            if canonical and canonical not in seen:
                seen.add(canonical)
                out.append(canonical)
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

def map_labels_to_registry_keys(labels: List[str]) -> List[str]:
    """Map human-friendly labels to registry keys using Config.LABEL_NAME_TO_KEY."""
    mapping = getattr(Config, "LABEL_NAME_TO_KEY", {})
    valid_keys = set(mapping.values())
    out, seen = [], set()
    for label in labels:
        norm = _normalize_label(label)
        key = mapping.get(norm)
        if not key and norm in valid_keys:
            key = norm
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
