# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
"""
LLM adapters dùng API URL đầy đủ (KHÔNG base_url, KHÔNG default URL).
- OpenAIChatLLM  : gọi trực tiếp endpoint /chat/completions
- OllamaChatLLM  : gọi trực tiếp endpoint /api/generate
"""

import json
import time
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
        api_url: str,          # BẮT BUỘC truyền vào
        timeout: int = 300,
        max_retries: int = 3,
        retry_delay: float = 1.5,
    ):
        if not api_url:
            raise ValueError("OllamaChatLLM: 'api_url' is required.")
        if not model:
            raise ValueError("OllamaChatLLM: 'model' is required.")

        self.model = model
        self.api_url = api_url
        self.timeout = int(timeout)
        self.max_retries = max(1, int(max_retries))
        self.retry_delay = float(retry_delay)

    def chat(self, system: str, user: str) -> str:
        # Ghép prompt theo format đơn giản [SYSTEM]...[USER]...
        prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{user}"
        payload = {"model": self.model, "prompt": prompt, "stream": True}

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with requests.post(
                    self.api_url,
                    json=payload,
                    timeout=self.timeout,
                    stream=True,
                ) as resp:
                    resp.raise_for_status()

                    chunks: list[str] = []
                    start_time = time.time()
                    last_tick = start_time
                    chunk_idx = 0

                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        try:
                            event = json.loads(raw_line)
                        except json.JSONDecodeError as exc:
                            print(f"[OllamaChatLLM] Bỏ qua chunk không hợp lệ: {exc}", file=sys.stderr, flush=True)
                            continue

                        if event.get("error"):
                            raise RuntimeError(f"Ollama error: {event['error']}")

                        piece = event.get("response") or ""
                        if piece:
                            chunk_idx += 1
                            now = time.time()
                            delta_ms = int((now - last_tick) * 1000)
                            total_ms = int((now - start_time) * 1000)
                            # Log chunk-level latency to track streaming speed.
                            print(
                                f"[OllamaChatLLM] chunk#{chunk_idx} dt={delta_ms}ms total={total_ms}ms len={len(piece)}",
                                file=sys.stderr,
                                flush=True,
                            )
                            chunks.append(piece)
                            last_tick = now

                        if event.get("done"):
                            break

                    return "".join(chunks).strip()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                wait_seconds = self.retry_delay * (2 ** (attempt - 1))
                print(
                    f"[OllamaChatLLM] Lỗi kết nối ({exc}). Thử lại {attempt + 1}/{self.max_retries} sau {wait_seconds:.1f}s.",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(wait_seconds)
            except requests.exceptions.RequestException as exc:
                raise RuntimeError(f"Ollama request failed: {exc}") from exc

        if last_error is not None:
            raise RuntimeError(f"Ollama connection failed after {self.max_retries} attempts: {last_error}") from last_error
        raise RuntimeError("OllamaChatLLM: Failed to generate response.")
