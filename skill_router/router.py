#!/usr/bin/env python3
"""router.py — Skill 路由主入口（事件驱动 + 后台 worker）"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from queue import Queue, Empty
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .scanner import ScanResult
from .config import Config
from .embedding import EmbeddingProvider
from .registry import SkillRegistry
from .search import SkillSearcher, SearchResult

logger = logging.getLogger(__name__)

# ── Watchdog availability ────────────────────────────────────────────

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileDeletedEvent
    _WATCHDOG_AVAILABLE = True
except Exception:
    _WATCHDOG_AVAILABLE = False


class _SkillDirHandler(FileSystemEventHandler if _WATCHDOG_AVAILABLE else object):
    """处理 skills 安装目录的文件系统事件"""

    def __init__(self, router: "SkillRouter", event_queue: Queue):
        self.router = router
        self.event_queue = event_queue

    def on_created(self, event):
        if event.is_directory or event.src_path.endswith("SKILL.md"):
            self.event_queue.put(("create", Path(event.src_path).parent))

    def on_deleted(self, event):
        if event.is_directory or event.src_path.endswith("SKILL.md"):
            self.event_queue.put(("delete", Path(event.src_path).parent))


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
            vectors_dir=config.vectors_dir,
            embedding=self.embedding,
        )
        self.searcher = SkillSearcher(self.registry, self.embedding)

        # ── Background sync state ──────────────────────────────────
        self._started = False
        self._start_lock = threading.Lock()
        self._event_queue: Queue = Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._observer: Optional[Observer] = None

        # Sync state file
        self._sync_state_path = config.db_path.parent / "sync_state.json"

    # ── Lifecycle ────────────────────────────────────────────────────

    def _start_background_services(self):
        with self._start_lock:
            if self._started:
                return
            self._started = True

            self._worker_thread = threading.Thread(target=self._sync_loop, daemon=True, name="SkillSync")
            self._worker_thread.start()

            if _WATCHDOG_AVAILABLE:
                self._observer = Observer()
                handler = _SkillDirHandler(self, self._event_queue)
                install_dir = self._skills_install_dir()
                if install_dir.exists():
                    self._observer.schedule(handler, str(install_dir), recursive=False)
                    self._observer.start()
                    logger.info(f"File-system watcher active on {install_dir}")
            else:
                logger.info("watchdog unavailable — using periodic polling")

    def _sync_loop(self):
        """后台同步循环：处理文件系统事件 + 标记 pending skills 为 ready"""
        poll_interval = 30 if not _WATCHDOG_AVAILABLE else 5

        while True:
            time.sleep(poll_interval)

            # 1. 处理文件系统事件
            events: List[tuple] = []
            while True:
                try:
                    events.append(self._event_queue.get_nowait())
                except Empty:
                    break

            for kind, path in events:
                if kind == "delete":
                    self._handle_skill_removed(path)
                else:
                    self._handle_skill_added(path)

            # 2. 将所有 vector 文件已写入但 status='pending' 的 skills 标记为 ready
            self._process_pending_skills()

            # 3. 增量目录扫描（无 watchdog 时）
            if not _WATCHDOG_AVAILABLE:
                self._incremental_scan()

    def _handle_skill_added(self, skill_path: Path):
        """处理新增 skill（来自文件系统事件）"""
        if not (skill_path / "SKILL.md").exists():
            return
        try:
            skill_id = self.registry.register(str(skill_path))
            logger.info(f"Auto-indexed new skill: {skill_path.name} (id={skill_id})")
        except Exception as e:
            logger.warning(f"Failed to auto-index {skill_path.name}: {e}")

    def _handle_skill_removed(self, skill_path: Path):
        """处理删除的 skill（来自文件系统事件）"""
        conn = self.registry._conn()
        row = conn.execute(
            "SELECT skill_id FROM skills WHERE path=?", (str(skill_path),)
        ).fetchone()
        conn.close()
        if row:
            self.registry.unregister(skill_path.name)
            logger.info(f"Auto-removed stale skill: {skill_path.name}")

    def _process_pending_skills(self):
        """将 pending skills 中向量文件已就绪的标记为 ready"""
        pending = self.registry.get_pending_skills()
        for skill in pending:
            vec_path = self.registry._vector_path(skill["skill_id"])
            if vec_path.exists():
                self.registry.mark_ready(skill["skill_id"])
                logger.debug(f"Skill {skill['skill_name']} marked ready")
            else:
                # 向量文件还没写入（不太可能，register 是同步的）
                pass

    def _incremental_scan(self):
        """无 watchdog 时：定期全量扫描（优化版，不做全量集合比对）"""
        try:
            install_dir = self._skills_install_dir()
            if not install_dir.exists():
                return

            EXCLUDE_DIRS = {".git", "__pycache__", ".DS_Store", "node_modules"}
            skill_router_dir = self._skill_dir()

            all_skills = {
                d for d in install_dir.iterdir()
                if d.is_dir()
                and d.name not in EXCLUDE_DIRS
                and d != skill_router_dir
                and (d / "SKILL.md").exists()
            }

            registered_paths = self.registry.list_skill_paths()

            new_skills = all_skills - registered_paths
            stale_paths = registered_paths - all_skills

            if stale_paths:
                removed = self.registry.remove_stale(all_skills)
                if removed > 0:
                    logger.info(f"Removed {removed} stale skills from registry")

            for skill_path in new_skills:
                try:
                    skill_id = self.registry.register(str(skill_path))
                    logger.info(f"Indexed new skill: {skill_path.name} (id={skill_id})")
                except Exception as e:
                    logger.warning(f"Failed to index new skill {skill_path.name}: {e}")

            self._save_sync_time()

        except Exception as e:
            logger.error(f"Incremental scan failed: {e}")

    def _save_sync_time(self):
        try:
            self._sync_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._sync_state_path.write_text(json.dumps({"last_sync": time.time()}))
        except Exception:
            pass

    def _load_sync_time(self) -> float:
        try:
            if self._sync_state_path.exists():
                return json.loads(self._sync_state_path.read_text()).get("last_sync", 0)
        except Exception:
            pass
        return 0

    # ── Helpers (import from config inline to avoid circular) ──────────

    def _skill_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def _skills_install_dir(self) -> Path:
        return self._skill_dir().parent

    # ── Public API ───────────────────────────────────────────────────

    def route(self, task: str, top_k: int = 5) -> List[SearchResult]:
        """将任务路由到最合适的 Skill"""
        # 懒启动后台服务（首次 route 触发）
        self._start_background_services()
        return self.searcher.search(task, top_k)

    def install(
        self,
        skill_path: str,
        *,
        scan_mode: str = "prompt",
    ) -> tuple[int, Optional["ScanResult"]]:
        """安装并注册新 Skill（安装前进行安全扫描）"""
        from .scanner import pre_install_scan, SecurityScanFailed, is_scanner_available

        scan_result = None

        if scan_mode != "skip" and is_scanner_available():
            scan_result = pre_install_scan(skill_path, scan_mode)

        # register 同步完成 embedding + 向量写入 + INSERT status='pending'
        skill_id = self.registry.register(skill_path)

        # 立即标记为 ready（register 已完成所有同步工作）
        self.registry.mark_ready(skill_id)

        return skill_id, scan_result

    def list_skills(self) -> List[dict]:
        """列出所有已注册（ready）Skills"""
        return self.registry.list_skills()

    def list_all_skills(self) -> List[dict]:
        """列出所有 Skills（含 pending/failed）"""
        return self.registry.get_all_skills()

    def uninstall(self, skill_name: str) -> bool:
        """卸载 Skill"""
        return self.registry.unregister(skill_name)

    def count(self) -> int:
        return self.registry.count()

    def count_all(self) -> dict:
        return self.registry.count_all()

    @classmethod
    def create(cls) -> "SkillRouter":
        """工厂方法：从 .env 加载配置"""
        return cls(Config.create())
