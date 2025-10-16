# -*- coding: utf-8 -*-
"""
finetune_v2 package: semantic-label variant of the editor pipeline.

The original `editor` package keeps the LLM-based classifier. finetune_v2
reuses the same registry and editing logic but swaps the classification step
for a FAISS-powered semantic similarity lookup.
"""

from editor import Config  # re-export configuration for convenience
from .pipeline import SemanticEditorPipeline

__all__ = [
    "Config",
    "SemanticEditorPipeline",
]
