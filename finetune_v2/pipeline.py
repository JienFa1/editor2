# -*- coding: utf-8 -*-
"""
SemanticEditorPipeline: editor pipeline variant that replaces the LLM-based
classifier with a FAISS semantic similarity matcher.
"""

from __future__ import annotations

import time
from typing import List, Tuple

from editor.Registry import PromptRegistry
from editor.chunking import Chunk, split_text
from editor.classifier import map_labels_to_registry_keys
from editor.llm import BaseLLM
from editor.pipeline import ChunkResult

from .label_matcher import LabelSemanticMatcher


class SemanticEditorPipeline:
    """Pipeline that maps paragraphs to labels via semantic search."""

    def __init__(
        self,
        *,
        editor_llm: BaseLLM,
        registry: PromptRegistry,
        matcher: LabelSemanticMatcher,
    ):
        self.editor_llm = editor_llm
        self.registry = registry
        self.matcher = matcher

    def _classify_with_semantics(self, text: str) -> List[str]:
        """Use FAISS semantic matcher to retrieve registry label keys."""
        label_names = self.matcher.labels_for_text(text)
        label_keys = map_labels_to_registry_keys(label_names)
        if not label_keys:
            raise ValueError("Semantic matcher returned no valid labels.")
        return label_keys

    def process(self, big_text: str) -> Tuple[str, List[ChunkResult]]:
        chunks: List[Chunk] = split_text(big_text)
        results: List[ChunkResult] = []

        for chunk in chunks:
            label_keys = self._classify_with_semantics(chunk.text)
            system_prompt, selected_labels, edit_prompt_ids = self.registry.build_system_prompt(label_keys)

            user_msg = "Bạn thực hiện chỉnh sửa đoạn văn sau.\n\nĐoạn văn:\n" + chunk.text

            t0 = time.time()
            edited_text = self.editor_llm.chat(system_prompt, user_msg)
            latency_ms = int((time.time() - t0) * 1000)

            results.append(
                ChunkResult(
                    chunk_id=chunk.chunk_id,
                    order=chunk.order,
                    labels=selected_labels,
                    edit_prompt_ids=edit_prompt_ids,
                    edited_text=(edited_text or "").strip(),
                    latency_ms=latency_ms,
                )
            )

        results.sort(key=lambda item: item.order)
        final_text = "\n\n".join(item.edited_text for item in results)
        return final_text, results

