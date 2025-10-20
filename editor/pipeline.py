# -*- coding: utf-8 -*-
import sys
import time
from dataclasses import dataclass, field
from typing import List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

"""
Baseline editor pipeline: classify + edit each paragraph sequentially.
"""

from editor.llm import BaseLLM
from editor.chunking import Chunk, split_text
from editor.Registry import PromptRegistry
from editor.classifier import build_classifier_prompt, parse_labels_json, map_labels_to_registry_keys


@dataclass
class ChunkResult:
    chunk_id: str
    order: int
    labels: List[str]
    edit_prompt_ids: List[str]
    edited_text: str
    latency_ms: int
    paragraph_indices: List[int] = field(default_factory=list)


class EditorPipeline:
    """Sequential pipeline that classifies and edits each chunk using the same LLM."""

    def __init__(self, classifier_llm: BaseLLM, editor_llm: BaseLLM, registry: PromptRegistry):
        self.classifier_llm = classifier_llm
        self.editor_llm = editor_llm
        self.registry = registry

    def _classify_labels(self, text: str) -> List[str]:
        sys_prompt, user_template = build_classifier_prompt()
        user_message = user_template.replace("{{TEXT}}", text)
        raw = self.classifier_llm.chat(sys_prompt, user_message)
        parsed_labels = parse_labels_json(raw)
        labels = map_labels_to_registry_keys(parsed_labels)
        if not labels:
            raise ValueError("Classifier returned empty/invalid labels for a chunk.")
        return labels

    def process(self, big_text: str) -> Tuple[str, List[ChunkResult]]:
        chunks: List[Chunk] = split_text(big_text)

        results: List[ChunkResult] = []
        for ck in chunks:
            labels = self._classify_labels(ck.text)
            system_prompt, selected_labels, ep_ids = self.registry.build_system_prompt(labels)
            user_msg = "Ban thuc hien chinh sua doan van sau.\n\nDoan van:\n" + ck.text
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
                    paragraph_indices=[ck.order - 1],
                )
            )

        results.sort(key=lambda item: item.order)
        final_text = "\n\n".join(item.edited_text for item in results)
        return final_text, results
