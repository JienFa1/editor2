# -*- coding: utf-8 -*-
"""
LLM adapters dùng API URL đầy đủ (KHÔNG base_url, KHÔNG default URL).
- OpenAIChatLLM  : gọi trực tiếp endpoint /chat/completions
- OllamaChatLLM  : gọi trực tiếp endpoint /api/generate
"""

from __future__ import annotations
import json
import requests
from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Giao diện tối giản: chat(system, user) -> str"""

    @abstractmethod
    def chat(self, system: str, user: str) -> str:
        raise NotImplementedError


class OpenAIChatLLM(BaseLLM):
    """
    OpenAI Chat Completions (API URL đầy đủ).
    - api_url: ví dụ "https://api.openai.com/v1/chat/completions" (BẮT BUỘC truyền vào)
    - model : ví dụ "gpt-4o-mini"
    - api_key: khóa OpenAI của bạn
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        api_url: str,           # BẮT BUỘC
        temperature: float = 0.2,
        timeout: int = 120,
    ):
        if not api_url:
            raise ValueError("OpenAIChatLLM: 'api_url' is required.")
        if not model:
            raise ValueError("OpenAIChatLLM: 'model' is required.")
        if not api_key:
            raise ValueError("OpenAIChatLLM: 'api_key' is required.")

        self.model = model
        self.api_key = api_key
        self.api_url = api_url
        self.temperature = float(temperature)
        self.timeout = int(timeout)

    def chat(self, system: str, user: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": self.temperature,
        }
        resp = requests.post(self.api_url, headers=headers, data=json.dumps(payload), timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()


class OllamaChatLLM(BaseLLM):
    """
    Ollama Local (API URL đầy đủ).
    - api_url: ví dụ "http://localhost:11434/api/generate" (BẮT BUỘC truyền vào)
    - model : ví dụ "llama3.1:8b-instruct-q6_K"
    """

    def __init__(
        self,
        *,
        model: str,
        api_url: str,          # BẮT BUỘC
        timeout: int = 180,
    ):
        if not api_url:
            raise ValueError("OllamaChatLLM: 'api_url' is required.")
        if not model:
            raise ValueError("OllamaChatLLM: 'model' is required.")

        self.model = model
        self.api_url = api_url
        self.timeout = int(timeout)

    def chat(self, system: str, user: str) -> str:
        # Ghép prompt theo format đơn giản [SYSTEM]...[USER]...
        prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{user}"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        resp = requests.post(self.api_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip()
