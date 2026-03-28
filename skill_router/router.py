#!/usr/bin/env python3
"""router.py — Skill 路由主入口"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .scanner import ScanResult
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

    def install(
        self,
        skill_path: str,
        *,
        scan_mode: str = "prompt",
    ) -> tuple[int, Optional["ScanResult"]]:
        """安装并注册新 Skill（安装前进行安全扫描）

        Args:
            skill_path: Skill 目录路径
            scan_mode: 扫描模式 ("fast", "deep", "skip", "prompt")
                - "prompt": 交互式选择（CLI 使用）
                - "fast": 快速扫描（静态分析）
                - "deep": 深度扫描（静态+LLM）
                - "skip": 跳过扫描

        Returns:
            tuple (skill_id, scan_result)
            scan_result 在 scan_mode="skip" 或 scanner 未安装时为 None

        Raises:
            SecurityScanFailed: 安全扫描发现威胁时抛出
        """
        from .scanner import pre_install_scan, SecurityScanFailed, is_scanner_available

        scan_result = None

        if scan_mode != "skip" and is_scanner_available():
            scan_result = pre_install_scan(skill_path, scan_mode)

        skill_id = self.registry.register(skill_path)
        return skill_id, scan_result

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
        """工厂方法：优先从 .env 加载配置，fallback 到 OpenClaw"""
        return cls(Config.create())
