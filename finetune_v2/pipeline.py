# -*- coding: utf-8 -*-
"""
SemanticEditorPipeline: replace the classifier with FAISS semantic search.
"""

from __future__ import annotations

import unicodedata
import time
from typing import Dict, List, Tuple

from editor import Config as EditorConfig
from editor.Registry import PromptRegistry
from editor.chunking import Chunk, split_text
from editor.classifier import map_labels_to_registry_keys
from editor.llm import BaseLLM
from editor.pipeline import ChunkResult

from .label_matcher import LabelSemanticMatcher


class SemanticEditorPipeline:
    """Pipeline that maps paragraphs to labels via semantic similarity."""

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
        label_names = self.matcher.labels_for_text(text)
        label_keys = map_labels_to_registry_keys(label_names)
        if not label_keys:
            raise ValueError("Semantic matcher returned no valid labels.")
        return label_keys

    @staticmethod
    def _resolve_title_label_key() -> str:
        """Find the configured label key that corresponds to the document title."""
        mapping = getattr(EditorConfig, "LABEL_NAME_TO_KEY", {}) or {}
        targets = {"tieude", "title"}
        for name, key in mapping.items():
            normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
            normalized = "".join(ch for ch in normalized if ch.isalnum())
            if normalized in targets:
                return key
        return mapping.get("tittle", "tittle")

    def process(self, big_text: str) -> Tuple[str, List[ChunkResult]]:
        chunks: List[Chunk] = split_text(big_text)
        if not chunks:
            return "", []

        classified: List[Tuple[Chunk, List[str]]] = []
        for chunk in chunks:
            label_keys = self._classify_with_semantics(chunk.text)
            classified.append((chunk, label_keys))

        title_label_key = self._resolve_title_label_key()

        title_entries: List[Tuple[Chunk, List[str]]] = []
        segments: List[Dict[str, object]] = []

        for chunk, label_keys in classified:
            paragraph_index = chunk.order - 1
            if title_label_key and title_label_key in label_keys:
                title_entries.append((chunk, label_keys))
                continue
            segments.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "order": chunk.order,
                    "text": chunk.text,
                    "label_keys": label_keys,
                    "paragraph_indices": [paragraph_index],
                }
            )

        if title_entries:
            combined_text = "\n\n".join(chunk.text for chunk, _ in title_entries)
            combined_order = min(chunk.order for chunk, _ in title_entries)
            combined_chunk_id = "+".join(chunk.chunk_id for chunk, _ in title_entries) or "TITLE_COMBINED"
            combined_labels = [title_label_key] if title_label_key else sorted(
                {key for _chunk, keys in title_entries for key in keys}
            )
            ordered_indices = [
                entry_chunk.order - 1
                for entry_chunk, _ in sorted(title_entries, key=lambda item: item[0].order)
            ]
            segments.append(
                {
                    "chunk_id": combined_chunk_id,
                    "order": combined_order,
                    "text": combined_text,
                    "label_keys": combined_labels,
                    "paragraph_indices": ordered_indices,
                }
            )

        results: List[ChunkResult] = []

        for segment in sorted(segments, key=lambda item: item["order"]):
            label_keys = segment["label_keys"]
            if not label_keys:
                raise ValueError("Segment is missing label keys after merging.")

            system_prompt, selected_labels, edit_prompt_ids = self.registry.build_system_prompt(label_keys)

            user_msg = "Ban thuc hien chinh sua doan van sau.\n\nDoan van:\n" + segment["text"]

            t0 = time.time()
            edited_text = self.editor_llm.chat(system_prompt, user_msg)
            latency_ms = int((time.time() - t0) * 1000)

            results.append(
                ChunkResult(
                    chunk_id=str(segment["chunk_id"]),
                    order=int(segment["order"]),
                    labels=selected_labels,
                    edit_prompt_ids=edit_prompt_ids,
                    edited_text=(edited_text or "").strip(),
                    latency_ms=latency_ms,
                    paragraph_indices=list(segment.get("paragraph_indices", [])),
                )
            )

        results.sort(key=lambda item: item.order)
        final_text = "\n\n".join(item.edited_text for item in results)
        return final_text, results
