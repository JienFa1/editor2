# -*- coding: utf-8 -*-


"""editor package: exposes pipeline components."""

__version__ = "0.1.0"

# Re-export cáº¥u hÃ¬nh
from . import Config  # noqa: F401

# Registry (label -> edit_prompts -> system_prompt)
from .Registry import PromptRegistry  # noqa: F401

# Äá»c .docx -> paragraphs -> big_text
from .docx_load import (  # noqa: F401
    read_paragraphs_from_config,
    paragraphs_to_big_text,
    document_to_big_text,
)

# Cáº¯t big_text theo Ä‘oáº¡n (má»—i paragraph -> 1 Chunk)
from .chunking import Chunk, split_text  # noqa: F401

# classifier cho bÆ°á»›c gÃ¡n nhÃ£n (prompt & parser)
from .classifier import build_classifier_prompt, parse_labels_json  # noqa: F401

# LLM adapters (OpenAI / Ollama) + interface
from .llm import BaseLLM, OpenAIChatLLM, OllamaChatLLM  # noqa: F401

# Pipeline tuáº§n tá»± end-to-end
from .pipeline import EditorPipeline, ChunkResult  # noqa: F401

# Export tiá»‡n Ã­ch (chá»‰ lÆ°u final_text ra .txt)
from .export_local import save_final_text_txt  # noqa: F401

__all__ = [
    "__version__",
    "Config",
    "PromptRegistry",
    "read_paragraphs_from_config",
    "paragraphs_to_big_text",
    "document_to_big_text",
    "Chunk",
    "split_text",
    "build_classifier_prompt",
    "parse_labels_json",
    "BaseLLM",
    "OpenAIChatLLM",
    "OllamaChatLLM",
    "EditorPipeline",
    "ChunkResult",
    "save_final_text_txt",
]
