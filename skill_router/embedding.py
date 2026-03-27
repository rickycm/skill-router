#!/usr/bin/env python3
"""embedding.py — Embedding 模型封装（支持 OpenAI 兼容 API / Ollama）"""

import httpx
import os
from typing import List


class EmbeddingProvider:
    def __init__(self, provider: str, api_key: str, base_url: str, model: str, dimensions: int):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimensions = dimensions

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "ollama":
            return self._embed_ollama(texts)
        else:
            return self._embed_openai(texts)

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """OpenAI 兼容接口（Gitee AI / OpenAI / Azure / SiliconFlow 等）"""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "input": [t[:8000] for t in texts],
        }
        r = httpx.post(
            f"{self.base_url.rstrip('/')}/embeddings",
            json=payload,
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        return [item["embedding"] for item in r.json()["data"]]

    def _embed_ollama(self, texts: List[str]) -> List[List[float]]:
        """Ollama 本地模型"""
        results = []
        for text in texts:
            r = httpx.post(
                f"{self.base_url.rstrip('/')}/api/embeddings",
                json={"model": self.model, "prompt": text[:8000]},
                timeout=60,
            )
            r.raise_for_status()
            results.append(r.json()["embedding"])
        return results
