# -*- coding: utf-8 -*-
"""
Debug script: in ra màn hình từng bước sau khi gán nhãn cho toàn bộ các chunk.

Chạy:
    python debug_semantic_pipeline.py --docx path/to/file.docx
hoặc để trống --docx sẽ dùng Config.DOCUMENT.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from editor import Config
from editor.Registry import PromptRegistry
from editor.classifier import map_labels_to_registry_keys
from editor.docx_load import document_to_big_text
from editor.chunking import split_text

from finetune_v2.label_matcher import (
    LabelSemanticIndex,
    LabelSemanticMatcher,
    SentenceTransformerEmbedder,
)


class DummyLLM:
    """LLM mock chỉ in prompt và trả về văn bản placeholder."""

    def chat(self, system: str, user: str) -> str:
        print("\n--- [LLM] System prompt ---")
        print(system)
        print("\n--- [LLM] User message ---")
        print(user)
        return "[LLM OUTPUT PLACEHOLDER]"


def load_matcher() -> LabelSemanticMatcher:
    index = LabelSemanticIndex.load(Config.FAISS_INDEX_PATH, Config.FAISS_METADATA_PATH)
    embedder = SentenceTransformerEmbedder(
        Config.EMBEDDING_MODEL_NAME,
        device=getattr(Config, "EMBEDDING_DEVICE", None),
    )
    return LabelSemanticMatcher(
        index=index,
        embedder=embedder,
        top_k=getattr(Config, "SIMILARITY_TOP_K", 1),
        threshold=getattr(Config, "SIMILARITY_THRESHOLD", None),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug pipeline từng bước.")
    parser.add_argument(
        "--docx",
        type=Path,
        default=None,
        help="Đường dẫn file DOCX. Nếu bỏ trống sẽ dùng Config.DOCUMENT.",
    )
    args = parser.parse_args()

    if args.docx:
        Config.DOCUMENT = str(args.docx.resolve())

    big_text = document_to_big_text()
    chunks = split_text(big_text)
    registry = PromptRegistry.from_dict(Config.REGISTRY_DICT)
    matcher = load_matcher()
    llm = DummyLLM()

    print(f"Tổng cộng {len(chunks)} chunk.")

    for chunk in chunks:
        print("\n==============================")
        print(f"Chunk {chunk.chunk_id} (order={chunk.order})")
        print(chunk.text)

        label_names = matcher.labels_for_text(chunk.text)
        label_keys = map_labels_to_registry_keys(label_names)
        print(f"Label names: {label_names}")
        print(f"Label keys: {label_keys}")

        system_prompt, selected_labels, edit_ids = registry.build_system_prompt(label_keys)
        print(f"Selected labels: {selected_labels}")
        print(f"Edit prompt IDs: {edit_ids}")

        user_msg = "Bạn thực hiện chỉnh sửa đoạn văn sau.\n\nĐoạn văn:\n" + chunk.text
        result = llm.chat(system_prompt, user_msg)
        print("\n--- [LLM] Output ---")
        print(result)


if __name__ == "__main__":
    main()

