#!/usr/bin/env python3
"""router.py — Skill 路由主入口"""

from pathlib import Path
from typing import List, Optional
from .config import Config
from .embedding import EmbeddingProvider
from .registry import SkillRegistry
from .search import SkillSearcher, SearchResult


class SkillRouter:
    def __init__(self, config: Config):
        self.config = config
        self.embedding = EmbeddingProvider(
            provider=config.embedding_provider,
            api_key=config.embedding_api_key,
            base_url=config.embedding_base_url,
            model=config.embedding_model,
            dimensions=config.embedding_dimensions,
        )
        self.registry = SkillRegistry(
            db_path=config.db_path,
            vectors_path=config.vectors_path,
            embedding=self.embedding,
        )
        self.searcher = SkillSearcher(self.registry, self.embedding)

    def route(self, task: str, top_k: int = 5) -> List[SearchResult]:
        """将任务路由到最合适的 Skill"""
        return self.searcher.search(task, top_k)

    def install(self, skill_path: str) -> int:
        """安装并注册新 Skill"""
        return self.registry.register(skill_path)

    def list_skills(self) -> List[dict]:
        """列出所有已注册 Skills"""
        return self.registry.list_skills()

    def uninstall(self, skill_name: str) -> bool:
        """卸载 Skill"""
        return self.registry.unregister(skill_name)

    def count(self) -> int:
        return self.registry.count()

    @classmethod
    def create(cls) -> "SkillRouter":
        """工厂方法：从 OpenClaw 配置创建"""
        return cls(Config.from_openclaw())
