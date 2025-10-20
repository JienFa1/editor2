# -*- coding: utf-8 -*-
"""
Diagnostic runner for the semantic editor pipeline that prints CPU/RAM/GPU
resource usage after label assignment and right before sending a segment to
the Ollama editor LLM. Use this script when you need to confirm the machine
still has enough headroom (especially on the GPU) before the editing stage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None

from editor import Config as EditorConfig
from editor.Registry import PromptRegistry
from editor.chunking import Chunk, split_text
from editor.docx_load import document_to_big_text_with_mapping
from editor.export_local import save_document_with_edits, save_final_text_txt
from editor.llm import BaseLLM, OllamaChatLLM, OpenAIChatLLM
from editor.pipeline import ChunkResult

from finetune_v2.label_matcher import (
    LabelSemanticIndex,
    LabelSemanticMatcher,
    SentenceTransformerEmbedder,
)
from finetune_v2.docx_utils import build_paragraph_updates
from finetune_v2.pipeline import SemanticEditorPipeline

# ---------------------------------------------------------------------------
# Utility structures


@dataclass
class Segment:
    """Represents a chunk of text ready for the editing stage."""

    chunk_id: str
    order: int
    text: str
    label_keys: List[str]
    paragraph_indices: List[int]


# ---------------------------------------------------------------------------
# Resource inspection helpers


def _bytes_to_mb(value: int | float | None) -> float:
    if value is None:
        return 0.0
    return float(value) / (1024 * 1024)


def _gpu_stats_from_torch() -> List[Dict[str, Any]]:
    """Collect GPU statistics using torch if CUDA is available."""
    if torch is None or not torch.cuda.is_available():
        return []

    stats: List[Dict[str, Any]] = []
    device_count = torch.cuda.device_count()
    for idx in range(device_count):
        with torch.cuda.device(idx):
            props = torch.cuda.get_device_properties(idx)
            total = props.total_memory
            reserved = torch.cuda.memory_reserved(idx)
            allocated = torch.cuda.memory_allocated(idx)
            free_est = max(total - reserved, 0)
            stats.append(
                {
                    "index": idx,
                    "name": props.name,
                    "total_mb": round(_bytes_to_mb(total), 2),
                    "allocated_mb": round(_bytes_to_mb(allocated), 2),
                    "reserved_mb": round(_bytes_to_mb(reserved), 2),
                    "free_estimate_mb": round(_bytes_to_mb(free_est), 2),
                    "cuda_capacity": props.multi_processor_count,
                }
            )
    return stats


def _gpu_stats_from_nvidia_smi() -> List[Dict[str, Any]]:
    """Fallback GPU statistics using `nvidia-smi` if available."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []

    query = [
        "name",
        "memory.total",
        "memory.used",
        "memory.free",
        "utilization.gpu",
        "utilization.memory",
    ]
    cmd = [
        exe,
        f"--query-gpu={','.join(query)}",
        "--format=csv,noheader,nounits",
    ]

    try:
        output = subprocess.check_output(cmd, encoding="utf-8", stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    stats: List[Dict[str, Any]] = []
    for line in output.strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != len(query):
            continue
        stats.append(
            {
                "index": len(stats),
                "name": parts[0],
                "total_mb": float(parts[1]),
                "used_mb": float(parts[2]),
                "free_mb": float(parts[3]),
                "utilization_gpu_percent": float(parts[4]),
                "utilization_memory_percent": float(parts[5]),
            }
        )
    return stats


def collect_resource_snapshot() -> Dict[str, Any]:
    """Gather CPU, RAM, and GPU statistics for logging."""
    snapshot: Dict[str, Any] = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "platform": platform.platform(),
    }

    if psutil is not None:
        snapshot["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        vm = psutil.virtual_memory()
        snapshot["ram_total_mb"] = round(_bytes_to_mb(vm.total), 2)
        snapshot["ram_used_mb"] = round(_bytes_to_mb(vm.used), 2)
        snapshot["ram_available_mb"] = round(_bytes_to_mb(vm.available), 2)
        proc = psutil.Process()
        rss = proc.memory_info().rss
        snapshot["process_rss_mb"] = round(_bytes_to_mb(rss), 2)
    else:  # pragma: no cover - best-effort fallback
        snapshot["cpu_percent"] = None
        snapshot["ram_total_mb"] = None
        snapshot["ram_used_mb"] = None
        snapshot["ram_available_mb"] = None
        snapshot["notes"] = "psutil not installed; limited CPU/RAM metrics."

    gpu_stats = _gpu_stats_from_torch()
    if not gpu_stats:
        gpu_stats = _gpu_stats_from_nvidia_smi()
    snapshot["gpus"] = gpu_stats

    if not gpu_stats:
        snapshot.setdefault("notes", "No GPU metrics detected.")

    return snapshot


def print_resource_snapshot(segment: Segment, selected_labels: Sequence[str], edit_prompt_ids: Sequence[str]) -> Dict[str, Any]:
    """Collect and print resource metrics for the provided segment."""
    snapshot = collect_resource_snapshot()

    label_display = ", ".join(selected_labels) if selected_labels else "(no labels)"
    print("\n[ResourceCheck]")
    print(f"  chunk_id   : {segment.chunk_id}")
    print(f"  order      : {segment.order}")
    print(f"  labels     : {label_display}")
    print(f"  edit prompts: {', '.join(edit_prompt_ids) if edit_prompt_ids else '(none)'}")
    if snapshot.get("cpu_percent") is not None:
        print(
            "  CPU        : "
            f"{snapshot.get('cpu_percent', 0):.1f}% | RAM used "
            f"{snapshot.get('ram_used_mb', 0):.1f} MB / "
            f"{snapshot.get('ram_total_mb', 0):.1f} MB"
        )
    else:
        print("  CPU/RAM    : unavailable (psutil missing)")

    gpus = snapshot.get("gpus") or []
    if gpus:
        for gpu in gpus:
            if "allocated_mb" in gpu:
                print(
                    "  GPU#{index} {name}: alloc={allocated_mb} MB "
                    "reserved={reserved_mb} MB free~={free_estimate_mb} MB".format(**gpu)
                )
            else:
                print(
                    "  GPU#{index} {name}: used={used_mb} MB / {total_mb} MB "
                    "(util {utilization_gpu_percent}% / mem {utilization_memory_percent}%)".format(**gpu)
                )
    else:
        print("  GPU        : not detected or stats unavailable")

    if "process_rss_mb" in snapshot:
        print(f"  Process RSS: {snapshot['process_rss_mb']:.1f} MB")
    if snapshot.get("notes"):
        print(f"  Notes      : {snapshot['notes']}")

    return snapshot


# ---------------------------------------------------------------------------
# Pipeline helpers


def load_matcher_from_config() -> LabelSemanticMatcher:
    index = LabelSemanticIndex.load(EditorConfig.FAISS_INDEX_PATH, EditorConfig.FAISS_METADATA_PATH)
    embedder = SentenceTransformerEmbedder(
        EditorConfig.EMBEDDING_MODEL_NAME,
        device=getattr(EditorConfig, "EMBEDDING_DEVICE", None),
    )
    probe = embedder.encode(["__dim_check__"])
    embed_dim = probe.shape[1] if probe.ndim == 2 else probe.shape[0]
    if embed_dim != index.dimension:
        raise RuntimeError(
            "Embedding dimension mismatch between FAISS index and runtime model. "
            f"Index dimension={index.dimension}, model '{EditorConfig.EMBEDDING_MODEL_NAME}' -> {embed_dim}. "
            "Rebuild the index with finetune_v2/build_label_index.py or update Config.EMBEDDING_MODEL_NAME "
            "to match the index."
        )
    return LabelSemanticMatcher(
        index=index,
        embedder=embedder,
        top_k=getattr(EditorConfig, "SIMILARITY_TOP_K", 1),
        threshold=getattr(EditorConfig, "SIMILARITY_THRESHOLD", None),
    )


def choose_editor_llm() -> BaseLLM:
    if getattr(EditorConfig, "USE_OLLAMA", True):
        print("[Debug] Provider: Ollama")
        return OllamaChatLLM(model=EditorConfig.OLLAMA_MODEL, api_url=EditorConfig.OLLAMA_API_URL)

    print("[Debug] Provider: OpenAI")
    api_key = getattr(EditorConfig, "OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty in editor/Config.py")
    return OpenAIChatLLM(
        model=EditorConfig.OPENAI_MODEL,
        api_key=api_key,
        api_url=EditorConfig.OPENAI_API_URL,
    )


def _classify_chunks(pipeline: SemanticEditorPipeline, chunks: Iterable[Chunk]) -> List[Segment]:
    """Mirror SemanticEditorPipeline classification while keeping chunk metadata."""
    segments: List[Segment] = []
    title_entries: List[Segment] = []
    title_label_key = pipeline._resolve_title_label_key()

    for chunk in chunks:
        label_keys = pipeline._classify_with_semantics(chunk.text)
        segment = Segment(
            chunk_id=chunk.chunk_id,
            order=chunk.order,
            text=chunk.text,
            label_keys=label_keys,
            paragraph_indices=[chunk.order - 1],
        )
        if title_label_key and title_label_key in label_keys:
            title_entries.append(segment)
        else:
            segments.append(segment)

    if title_entries:
        combined_text = "\n\n".join(entry.text for entry in title_entries)
        combined_order = min(entry.order for entry in title_entries)
        combined_chunk_id = "+".join(entry.chunk_id for entry in title_entries) or "TITLE_COMBINED"
        combined_labels = sorted(set(key for entry in title_entries for key in entry.label_keys))
        combined_indices = sorted(idx for entry in title_entries for idx in entry.paragraph_indices)
        segments.append(
            Segment(
                chunk_id=combined_chunk_id,
                order=combined_order,
                text=combined_text,
                label_keys=combined_labels,
                paragraph_indices=combined_indices,
            )
        )

    return sorted(segments, key=lambda item: item.order)


def run_pipeline_with_resource_checks(
    pipeline: SemanticEditorPipeline,
    big_text: str,
    *,
    skip_edit: bool = False,
) -> Dict[str, Any]:
    """Execute the semantic pipeline with resource inspection before editing."""
    chunks = split_text(big_text)
    if not chunks:
        print("[Debug] No chunks found in the document.")
        return {"final_text": "", "results": [], "resource_logs": []}

    segments = _classify_chunks(pipeline, chunks)
    resource_logs: List[Dict[str, Any]] = []
    results: List[ChunkResult] = []

    for segment in segments:
        system_prompt, selected_labels, edit_prompt_ids = pipeline.registry.build_system_prompt(segment.label_keys)

        snapshot = print_resource_snapshot(segment, selected_labels, edit_prompt_ids)
        resource_logs.append(
            {
                "chunk_id": segment.chunk_id,
                "order": segment.order,
                "labels": list(selected_labels),
                "edit_prompt_ids": list(edit_prompt_ids),
                "resources": snapshot,
            }
        )

        user_msg = "B?n th?c hi?n ch?nh s?a do?n van sau.\n\nDo?n van:\n" + segment.text

        if skip_edit:
            edited_text = segment.text
            latency_ms = 0
        else:
            t0 = time.time()
            edited_text = pipeline.editor_llm.chat(system_prompt, user_msg)
            latency_ms = int((time.time() - t0) * 1000)

        results.append(
            ChunkResult(
                chunk_id=segment.chunk_id,
                order=segment.order,
                labels=list(selected_labels),
                edit_prompt_ids=list(edit_prompt_ids),
                edited_text=(edited_text or "").strip(),
                latency_ms=latency_ms,
                paragraph_indices=list(segment.paragraph_indices),
            )
        )

    final_text = "\n\n".join(item.edited_text for item in sorted(results, key=lambda x: x.order))
    return {"final_text": final_text, "results": results, "resource_logs": resource_logs}


# ---------------------------------------------------------------------------
# CLI handling


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run semantic pipeline with GPU/CPU resource inspection before the editing stage.",
    )
    parser.add_argument(
        "--docx",
        type=Path,
        default=None,
        help="Path to the DOCX input. Defaults to editor.Config.DOCUMENT.",
    )
    parser.add_argument(
        "--dump-json",
        type=Path,
        default=None,
        help="Optional path to store resource snapshots in JSON format.",
    )
    parser.add_argument(
        "--skip-edit",
        action="store_true",
        help="Skip calling the editor LLM (useful when only the resource check is needed).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write the final text to outputs/result_debug.txt.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    if args.docx:
        EditorConfig.DOCUMENT = str(args.docx.resolve())
        print(f"[Debug] Using DOCX: {EditorConfig.DOCUMENT}")
    else:
        print(f"[Debug] Using DOCX from Config: {EditorConfig.DOCUMENT}")

    big_text, document, paragraphs = document_to_big_text_with_mapping()

    registry = PromptRegistry.from_dict(EditorConfig.REGISTRY_DICT)
    matcher = load_matcher_from_config()
    editor_llm = choose_editor_llm()
    pipeline = SemanticEditorPipeline(editor_llm=editor_llm, registry=registry, matcher=matcher)

    outcome = run_pipeline_with_resource_checks(pipeline, big_text, skip_edit=args.skip_edit)
    final_text: str = outcome["final_text"]
    results: List[ChunkResult] = outcome["results"]
    resource_logs: List[Dict[str, Any]] = outcome["resource_logs"]
    paragraph_updates = build_paragraph_updates(results, paragraphs)
    docx_output_path = Path("./outputs/result_debug.docx")

    print("\n=== PIPELINE RESULTS ===")
    print(final_text if final_text else "(empty)")

    print("\n=== AUDIT TRAIL ===")
    for entry in results:
        print(
            {
                "chunk_id": entry.chunk_id,
                "order": entry.order,
                "labels": entry.labels,
                "edit_prompts": entry.edit_prompt_ids,
                "latency_ms": entry.latency_ms,
            }
        )

    if args.dump_json:
        payload = {
            "resource_logs": resource_logs,
            "results": [
                {
                    "chunk_id": entry.chunk_id,
                    "order": entry.order,
                    "labels": entry.labels,
                    "edit_prompts": entry.edit_prompt_ids,
                    "latency_ms": entry.latency_ms,
                }
                for entry in results
            ],
            "final_text": final_text,
            "docx_path": str(docx_output_path),
        }
        args.dump_json.parent.mkdir(parents=True, exist_ok=True)
        args.dump_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[Debug] Resource log written to {args.dump_json}")

    if not args.no_save:
        save_final_text_txt(final_text, out_path="./outputs/result_debug.txt")
        save_document_with_edits(document, paragraph_updates, out_path=str(docx_output_path))
        print("[Debug] Final text saved to outputs/result_debug.txt")
        print(f"[Debug] Edited DOCX saved to {docx_output_path}")


if __name__ == "__main__":
    main()
