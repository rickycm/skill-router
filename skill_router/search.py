#!/usr/bin/env python3
"""search.py — 检索逻辑（适配 per-skill vector 文件）"""

import numpy as np
from typing import List
from dataclasses import dataclass
from .registry import SkillRegistry
from .embedding import EmbeddingProvider


@dataclass
class SearchResult:
    skill_id: int
    skill_name: str
    description: str
    path: str
    score: float
    tags: list


class SkillSearcher:
    def __init__(self, registry: SkillRegistry, embedding: EmbeddingProvider):
        self.registry = registry
        self.embedding = embedding

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """语义检索，返回 top_k 个最相关的 Skill（仅 ready 状态）"""
        query_vec = np.array(self.embedding.embed_one(query), dtype=np.float32)

        # 加载所有 ready 状态的向量（直接按 skill_id 索引，不再用数组下标）
        skill_ids, vectors = self.registry._load_all_vectors()

        if vectors.shape[0] == 0:
            return []

        # 余弦相似度
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        normalized = vectors / (norms + 1e-8)
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
        similarities = np.dot(normalized, query_norm)

        # Top-K
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            skill_id = skill_ids[int(idx)]
            skill = self.registry.get_skill_by_id(skill_id)
            if skill:
                results.append(SearchResult(
                    skill_id=skill_id,
                    skill_name=skill["skill_name"],
                    description=skill["description"] or "",
                    path=skill["path"],
                    score=float(similarities[idx]),
                    tags=skill.get("tags", []),
                ))
        return results
