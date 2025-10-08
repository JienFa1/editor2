# -*- coding: utf-8 -*-
"""
editor_pipeline/pipeline.py — pipeline chính (CHẠY TUẦN TỰ)

Luồng xử lý:
1) Split   : cắt big_text theo ĐOẠN (paragraph) → List[Chunk]
2) Classify: gán 1..n nhãn hợp lệ cho từng Chunk bằng LLM
3) Build   : registry.build_system_prompt(labels)
4) Edit    : LẦN LƯỢT gọi LLM biên tập (KHÔNG dùng thread pool)
5) Join    : ghép kết quả theo thứ tự

Phụ thuộc các module bạn đã duyệt: config, registry, docx_ingest, chunking, utils, llm.
"""

import time
from dataclasses import dataclass
from typing import List, Tuple

from .llm import BaseLLM
from .chunking import split_text, Chunk
from .registry import PromptRegistry
from .utils import build_classifier_prompt, parse_labels_json


@dataclass
class ChunkResult:
    chunk_id: str
    order: int
    labels: List[str]
    edit_prompt_ids: List[str]
    edited_text: str
    latency_ms: int


class EditorPipeline:
    """Pipeline biên tập văn bản mục vụ (tuần tự)."""

    def __init__(self, classifier_llm: BaseLLM, editor_llm: BaseLLM, registry: PromptRegistry):
        self.classifier_llm = classifier_llm
        self.editor_llm = editor_llm
        self.registry = registry

    def _classify_labels(self, text: str) -> List[str]:
        sys, usr_tpl = build_classifier_prompt()
        user = usr_tpl.replace("{{TEXT}}", text)
        raw = self.classifier_llm.chat(sys, user)
        labels = parse_labels_json(raw)
        if not labels:
            raise ValueError("Classifier returned empty/invalid labels for a chunk.")
        return labels

    def process(self, big_text: str) -> Tuple[str, List[ChunkResult]]:
        chunks: List[Chunk] = split_text(big_text)

        results: List[ChunkResult] = []
        for ck in chunks:
            # B2) classify
            labels = self._classify_labels(ck.text)
            # B3) build system prompt
            system_prompt, selected_labels, ep_ids = self.registry.build_system_prompt(labels)
            # B4) edit (TUẦN TỰ)
            user_msg = "Bạn thực hiện chỉnh sửa đoạn văn sau.\n\nĐoạn văn:\n" + ck.text
            t0 = time.time()
            edited = self.editor_llm.chat(system_prompt, user_msg)
            dt = int((time.time() - t0) * 1000)
            results.append(
                ChunkResult(
                    chunk_id=ck.chunk_id,
                    order=ck.order,
                    labels=selected_labels,
                    edit_prompt_ids=ep_ids,
                    edited_text=(edited or "").strip(),
                    latency_ms=dt,
                )
            )

        # B5) join
        results.sort(key=lambda x: x.order)
        final_text = "\n\n".join(r.edited_text for r in results)
        return final_text, results
