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
        # 懒加载同步：检测并处理新增/删除的 skills
        self._sync_skills()
        return self.searcher.search(task, top_k)

    def _sync_skills(self) -> None:
        """懒加载同步：检测目录变化，新增索引，删除 stale entries"""
        import threading
        import logging

        logger = logging.getLogger(__name__)

        # 在后台线程执行，不阻塞路由
        def _do_sync():
            try:
                from .config import _skills_install_dir, _skill_dir

                install_dir = _skills_install_dir()
                skill_router_dir = _skill_dir()

                if not install_dir.exists():
                    return

                # 扫描安装目录中的所有 skill（排除 skill-router 自身）
                EXCLUDE_DIRS = {".git", "__pycache__", ".DS_Store", "node_modules"}
                all_skills = {
                    d for d in install_dir.iterdir()
                    if d.is_dir()
                    and d.name not in EXCLUDE_DIRS
                    and d != skill_router_dir
                    and (d / "SKILL.md").exists()
                }

                # 检查已注册的 skill
                registered_paths = self.registry.list_skill_paths()

                # 找出新增的 skill（在目录中但未注册）
                new_skills = all_skills - registered_paths

                # 删除 stale entries（已注册但目录中不存在）
                stale_paths = registered_paths - all_skills
                if stale_paths:
                    removed = self.registry.remove_stale(all_skills)
                    if removed > 0:
                        logger.info(f"Removed {removed} stale skills from registry")

                # 索引新增的 skills（静默扫描）
                for skill_path in new_skills:
                    try:
                        self._silent_index(skill_path)
                    except Exception as e:
                        logger.warning(f"Failed to index new skill {skill_path.name}: {e}")

            except Exception as e:
                logger.error(f"Skill sync failed: {e}")

        # 启动后台线程
        thread = threading.Thread(target=_do_sync, daemon=True)
        thread.start()

    def _silent_index(self, skill_path: Path) -> bool:
        """静默索引单个 skill（用于后台同步）"""
        import logging

        logger = logging.getLogger(__name__)

        try:
            # 尝试安全扫描（静默模式）
            from .scanner import pre_install_scan, SecurityScanFailed, is_scanner_available

            scan_result = None
            if is_scanner_available():
                try:
                    scan_result = pre_install_scan(skill_path, "fast")
                    logger.info(f"New skill passed security scan: {skill_path.name}")
                except SecurityScanFailed as e:
                    # 安全扫描未通过，记录警告但不阻止索引
                    logger.warning(
                        f"New skill {skill_path.name} failed security scan: "
                        f"{len(e.scan_result.findings)} findings"
                    )

            # 注册 skill
            skill_id = self.registry.register(str(skill_path))
            logger.info(f"Indexed new skill: {skill_path.name} (id={skill_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to index skill {skill_path.name}: {e}")
            return False

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
        """工厂方法：从 .env 加载配置"""
        return cls(Config.create())
