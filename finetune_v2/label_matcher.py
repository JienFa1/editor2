# -*- coding: utf-8 -*-
"""
Semantic label matching utilities backed by FAISS.

The matcher works in two stages:
1. During setup, label descriptions are embedded with SentenceTransformer
   and indexed in a cosine-similarity FAISS index.
2. At runtime, chunk texts are embedded on the fly and queried against the
   index to retrieve the most similar label names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import faiss  # type: ignore
import numpy as np
from sentence_transformers import SentenceTransformer


def _ensure_float32(matrix: np.ndarray) -> np.ndarray:
    """Ensure the numpy array is contiguous float32."""
    if matrix.dtype != np.float32:
        matrix = matrix.astype(np.float32, copy=False)
    if not matrix.flags["C_CONTIGUOUS"]:
        matrix = np.ascontiguousarray(matrix)
    return matrix


class SentenceTransformerEmbedder:
    """SentenceTransformer wrapper that always returns normalized vectors."""

    def __init__(self, model_name: str, *, device: Optional[str] = None):
        self.model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        embeddings = self.model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return _ensure_float32(embeddings)


@dataclass
class LabelEntry:
    """Metadata stored alongside each semantic label embedding."""

    name: str
    description: str


class LabelSemanticIndex:
    """Wrapper around a FAISS index plus label metadata."""

    def __init__(self, index: faiss.Index, entries: List[LabelEntry]):
        if not isinstance(index, faiss.Index):
            raise TypeError("index must be a faiss.Index instance")
        self.index = index
        self.entries = entries
        if len(entries) != index.ntotal:
            raise ValueError("Metadata entries count does not match index size.")

    @property
    def dimension(self) -> int:
        return self.index.d

    @property
    def label_names(self) -> List[str]:
        return [entry.name for entry in self.entries]

    @classmethod
    def load(cls, index_path: Path, metadata_path: Path) -> "LabelSemanticIndex":
        if not index_path.is_file():
            raise FileNotFoundError(f"Missing FAISS index at {index_path}")
        if not metadata_path.is_file():
            raise FileNotFoundError(f"Missing metadata file at {metadata_path}")

        index = faiss.read_index(str(index_path))
        with metadata_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        entries_data = meta.get("labels") or []
        entries = [
            LabelEntry(name=str(item.get("name", "")).strip(), description=str(item.get("description", "")).strip())
            for item in entries_data
        ]

        return cls(index=index, entries=entries)

    def search(self, query_vector: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        """Run a FAISS search with the provided (batch) query vectors."""
        query = _ensure_float32(query_vector)
        if query.ndim == 1:
            query = query.reshape(1, -1)
        return self.index.search(query, top_k)


class LabelSemanticMatcher:
    """High-level helper that turns raw text into ranked label names."""

    def __init__(
        self,
        index: LabelSemanticIndex,
        embedder: SentenceTransformerEmbedder,
        *,
        top_k: int = 1,
        threshold: Optional[float] = None,
    ):
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        self.index = index
        self.embedder = embedder
        self.top_k = top_k
        self.threshold = threshold

    def label_scores(self, text: str) -> List[Tuple[str, float]]:
        """Return (label_name, score) pairs sorted by similarity."""
        embedding = self.embedder.encode([text])
        distances, indices = self.index.search(embedding, self.top_k)
        distance_row = distances[0]
        index_row = indices[0]

        results: List[Tuple[str, float]] = []
        for idx, score in zip(index_row, distance_row):
            if idx < 0 or idx >= len(self.index.entries):
                continue
            if self.threshold is not None and score < self.threshold:
                continue
            label_name = self.index.entries[idx].name
            results.append((label_name, float(score)))
        return results

    def labels_for_text(self, text: str) -> List[str]:
        """Return label names ordered by semantic similarity."""
        return [name for name, _score in self.label_scores(text)]


def _normalize_description(text: str) -> str:
    return " ".join((text or "").split())


def build_index_from_descriptions(
    descriptions: Iterable[Tuple[str, str]],
    embedder: SentenceTransformerEmbedder,
) -> Tuple[faiss.Index, List[LabelEntry]]:
    """
    Build a cosine-similarity FAISS index from (label_name, description) pairs.
    """
    names: List[str] = []
    descs: List[str] = []
    for name, description in descriptions:
        norm_name = (name or "").strip()
        norm_desc = _normalize_description(description)
        if not norm_name or not norm_desc:
            continue
        names.append(norm_name)
        descs.append(norm_desc)

    if not names:
        raise ValueError("No valid label descriptions provided.")

    embeddings = embedder.encode(descs)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    entries = [LabelEntry(name=n, description=d) for n, d in zip(names, descs)]
    return index, entries


def save_index(
    index: faiss.Index,
    entries: Sequence[LabelEntry],
    *,
    index_path: Path,
    metadata_path: Path,
) -> None:
    """Persist the FAISS index and metadata to disk."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(index_path))
    meta_payload = {
        "version": 1,
        "embedding_dim": index.d,
        "labels": [{"name": entry.name, "description": entry.description} for entry in entries],
    }
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(meta_payload, f, ensure_ascii=False, indent=2)

