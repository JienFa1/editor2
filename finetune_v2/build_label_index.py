# -*- coding: utf-8 -*-
"""
Tiện ích dựng chỉ mục FAISS nhãn ngữ nghĩa cho finetune-v2.

Các bước:
1. Chỉnh sửa tệp JSON tại Config.LABEL_DESCRIPTIONS_PATH để mỗi tên nhãn
   trong registry có một đoạn mô tả.
2. Chạy `python -m finetune_v2.build_label_index`.
3. Script sẽ embedding các mô tả và lưu chỉ mục FAISS cùng metadata tại
   Config.FAISS_INDEX_PATH / Config.FAISS_METADATA_PATH.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple

from . import Config
from .label_matcher import SentenceTransformerEmbedder, build_index_from_descriptions, save_index


def _label_names_from_config() -> Dict[str, str]:
    """Trả về ánh xạ {label_name: label_key} để kiểm tra hợp lệ."""
    return {name: key for key, name in Config.LABEL_KEY_TO_NAME.items()}


def _create_template_file(path: Path) -> None:
    """Tạo tệp JSON khung chứa mô tả nhãn."""
    payload = [
        {
            "name": name,
            "description": f"TODO: mô tả cho nhãn '{name}'.",
        }
        for name in _label_names_from_config().keys()
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _load_descriptions(path: Path) -> Iterable[Tuple[str, str]]:
    if not path.is_file():
        _create_template_file(path)
        raise FileNotFoundError(
            f"Thiếu tệp mô tả nhãn. Đã tạo sẵn một khung tại {path}. "
            "Vui lòng điền các đoạn mô tả trước khi dựng lại chỉ mục."
        )

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    descriptions: Dict[str, str] = {}
    if isinstance(data, list):
        for entry in data:
            name = str(entry.get("name", "")).strip()
            desc = str(entry.get("description", "")).strip()
            if name:
                descriptions[name] = desc
    elif isinstance(data, dict):
        for name, desc in data.items():
            descriptions[str(name).strip()] = str(desc or "").strip()
    else:
        raise ValueError("Mô tả nhãn phải ở dạng danh sách đối tượng hoặc ánh xạ (dict).")

    expected_names = list(_label_names_from_config().keys())
    missing = sorted(set(expected_names) - set(descriptions.keys()))
    if missing:
        raise ValueError(f"Thiếu mô tả cho các nhãn: {missing}")

    return [(name, descriptions[name]) for name in expected_names]


def main() -> None:
    try:
        descriptions = _load_descriptions(Config.LABEL_DESCRIPTIONS_PATH)
    except Exception as exc:  # noqa: BLE001
        print(f"[label-index] Lỗi: {exc}", file=sys.stderr)
        sys.exit(1)

    embedder = SentenceTransformerEmbedder(
        Config.EMBEDDING_MODEL_NAME,
        device=Config.EMBEDDING_DEVICE,
    )
    index, entries = build_index_from_descriptions(descriptions, embedder)

    save_index(
        index,
        list(entries),
        index_path=Config.FAISS_INDEX_PATH,
        metadata_path=Config.FAISS_METADATA_PATH,
    )

    print(
        "[label-index] Đã dựng chỉ mục FAISS "
        f"(d={index.d}, labels={len(entries)}) -> {Config.FAISS_INDEX_PATH}"
    )


if __name__ == "__main__":
    main()
