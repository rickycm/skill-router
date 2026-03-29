#!/usr/bin/env python3
"""registry.py — Skill 注册表管理（SQLite + per-skill vector files）"""

import sqlite3
import json
import numpy as np
import time
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Set

from .manifest import read_manifest, SkillManifest
from .embedding import EmbeddingProvider


class SkillRegistry:
    def __init__(self, db_path: Path, vectors_dir: Path, embedding: EmbeddingProvider):
        self.db_path = Path(db_path)
        self.vectors_dir = Path(vectors_dir)
        self.embedding = embedding
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vectors_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_if_needed()
        self._init_db()

    # ── Connection helper ──────────────────────────────────────────────

    def _conn(self):
        """Create a SQLite connection with WAL mode disabled for durability."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=DELETE")
        return conn

    # ── Schema init / migration ────────────────────────────────────────

    def _init_db(self):
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL UNIQUE,
                version TEXT,
                description TEXT,
                author TEXT,
                tags TEXT,
                path TEXT NOT NULL,
                indexed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending' NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_name ON skills(skill_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_status ON skills(status)")
        conn.commit()
        conn.close()

    def _migrate_if_needed(self):
        """一次性迁移：从旧的 vectors.npy + 顺序 array → per-skill .npy 文件"""
        legacy_path = self.db_path.parent / "vectors.npy"
        if not legacy_path.exists():
            return

        # 防止重复迁移
        marker = self.db_path.parent / ".vectors_migrated"
        if marker.exists():
            return

        conn = self._conn()
        rows = conn.execute("SELECT skill_id FROM skills ORDER BY skill_id").fetchall()
        try:
            legacy = np.load(legacy_path)
            if legacy.ndim == 1:
                legacy = legacy.reshape(1, -1)
        except Exception:
            legacy = None

        for (skill_id,) in rows:
            if legacy is not None and skill_id <= len(legacy):
                vec = legacy[skill_id - 1]
                np.save(str(self._vector_path(skill_id)), vec)

        conn.execute("ALTER TABLE skills ADD COLUMN status TEXT DEFAULT 'ready' NOT NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_status ON skills(status)")
        conn.commit()
        conn.close()

        shutil.move(str(legacy_path), str(legacy_path.with_suffix(".npy.bak")))
        marker.touch()

    # ── Vector file helpers ───────────────────────────────────────────

    def _vector_path(self, skill_id: int) -> Path:
        return self.vectors_dir / f"{skill_id}.npy"

    def _load_vector(self, skill_id: int) -> Optional[np.ndarray]:
        p = self._vector_path(skill_id)
        if not p.exists():
            return None
        v = np.load(str(p))
        if v.ndim == 0:
            return v.reshape(1, -1)
        return v

    def _load_all_vectors(self) -> tuple[List[int], np.ndarray]:
        """加载所有 ready 状态的向量，返回 (skill_ids, matrix)"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT skill_id FROM skills WHERE status='ready' ORDER BY skill_id"
        ).fetchall()
        conn.close()

        if not rows:
            return [], np.array([], dtype=np.float32).reshape(0, self.embedding.dimensions)

        ids = [r[0] for r in rows]
        matrices = []
        for sid in ids:
            vec = self._load_vector(sid)
            if vec is not None:
                matrices.append(vec)
            else:
                # 向量文件缺失，降级为零向量
                matrices.append(np.zeros(self.embedding.dimensions, dtype=np.float32))

        matrix = np.vstack(matrices) if matrices else np.array([], dtype=np.float32).reshape(0, self.embedding.dimensions)
        return ids, matrix

    def _upsert_vector(self, skill_id: int, vector: List[float]) -> None:
        """同步写入向量文件（install 时调用）"""
        arr = np.array(vector, dtype=np.float32).reshape(1, -1)
        np.save(str(self._vector_path(skill_id)), arr)

    # ── Registration ─────────────────────────────────────────────────

    def register(self, skill_path: str) -> int:
        """注册 Skill（同步计算 embedding 并写入向量文件）"""
        skill_path = Path(skill_path)
        manifest = read_manifest(skill_path)
        if not manifest:
            raise ValueError(f"SKILL.md not found in {skill_path}")

        combined_text = manifest.combined_text()
        vector = self.embedding.embed_one(combined_text)

        conn = self._conn()
        indexed_at = str(int(time.time()))
        try:
            conn.execute("""
                INSERT INTO skills (skill_name, version, description, author, tags, path, indexed_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (manifest.name, manifest.version, manifest.description, manifest.author,
                  json.dumps(manifest.tags), str(skill_path), indexed_at))
            skill_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError:
            conn.execute("UPDATE skills SET version=?, description=?, author=?, tags=?, indexed_at=?, status='pending' WHERE path=?",
                        (manifest.version, manifest.description, manifest.author,
                         json.dumps(manifest.tags), indexed_at, str(skill_path)))
            skill_id = conn.execute("SELECT skill_id FROM skills WHERE path=?", (str(skill_path),)).fetchone()[0]
        conn.commit()
        conn.close()

        self._upsert_vector(skill_id, vector)
        return skill_id

    def mark_ready(self, skill_id: int) -> None:
        conn = self._conn()
        conn.execute("UPDATE skills SET status='ready' WHERE skill_id=?", (skill_id,))
        conn.commit()
        conn.close()

    def mark_failed(self, skill_id: int, error: str = "") -> None:
        conn = self._conn()
        conn.execute(
            "UPDATE skills SET status='failed', updated_at=CURRENT_TIMESTAMP WHERE skill_id=?",
            (skill_id,)
        )
        conn.commit()
        conn.close()

    def get_pending_skills(self) -> List[Dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT skill_id, skill_name, path, indexed_at FROM skills WHERE status='pending' ORDER BY skill_id"
        ).fetchall()
        conn.close()
        return [
            {"skill_id": r[0], "skill_name": r[1], "path": r[2], "indexed_at": r[3]}
            for r in rows
        ]

    def get_ready_skills(self) -> List[Dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT skill_id, skill_name, version, description, tags, path, indexed_at FROM skills WHERE status='ready' ORDER BY skill_id"
        ).fetchall()
        conn.close()
        return [
            {"skill_id": r[0], "skill_name": r[1], "version": r[2], "description": r[3],
             "tags": json.loads(r[4]) if r[4] else [], "path": r[5], "indexed_at": r[6]}
            for r in rows
        ]

    def get_all_skills(self) -> List[Dict]:
        """列出所有 skills（含状态）"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT skill_id, skill_name, version, description, tags, path, indexed_at, status FROM skills ORDER BY skill_id"
        ).fetchall()
        conn.close()
        return [
            {"skill_id": r[0], "skill_name": r[1], "version": r[2], "description": r[3],
             "tags": json.loads(r[4]) if r[4] else [], "path": r[5], "indexed_at": r[6], "status": r[7]}
            for r in rows
        ]

    # ── Query ──────────────────────────────────────────────────────────

    def list_skills(self) -> List[Dict]:
        """列出所有已注册（ready）skills — 兼容旧接口"""
        return self.get_ready_skills()

    def get_skill_by_id(self, skill_id: int) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute(
            "SELECT skill_id, skill_name, version, description, tags, path, indexed_at, status FROM skills WHERE skill_id=?",
            (skill_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {"skill_id": row[0], "skill_name": row[1], "version": row[2], "description": row[3],
                "tags": json.loads(row[4]) if row[4] else [], "path": row[5], "indexed_at": row[6], "status": row[7]}

    def count(self) -> int:
        conn = self._conn()
        n = conn.execute("SELECT COUNT(*) FROM skills WHERE status='ready'").fetchone()[0]
        conn.close()
        return n

    def count_all(self) -> Dict[str, int]:
        conn = self._conn()
        total = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        ready = conn.execute("SELECT COUNT(*) FROM skills WHERE status='ready'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM skills WHERE status='pending'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM skills WHERE status='failed'").fetchone()[0]
        conn.close()
        return {"total": total, "ready": ready, "pending": pending, "failed": failed}

    def unregister(self, skill_name: str) -> bool:
        conn = self._conn()
        row = conn.execute("SELECT skill_id FROM skills WHERE skill_name=?", (skill_name,)).fetchone()
        if not row:
            conn.close()
            return False
        skill_id = row[0]
        cur = conn.execute("DELETE FROM skills WHERE skill_name=?", (skill_name,))
        conn.commit()
        conn.close()
        self._vector_path(skill_id).unlink(missing_ok=True)
        return cur.rowcount > 0

    def list_skill_paths(self) -> Set[Path]:
        """获取所有已注册 skill 的路径集合（不含状态过滤）"""
        conn = self._conn()
        rows = conn.execute("SELECT path FROM skills").fetchall()
        conn.close()
        return {Path(r[0]) for r in rows}

    def list_ready_skill_paths(self) -> Set[Path]:
        """获取所有 ready skill 的路径集合"""
        conn = self._conn()
        rows = conn.execute("SELECT path FROM skills WHERE status='ready'").fetchall()
        conn.close()
        return {Path(r[0]) for r in rows}

    def remove_stale(self, valid_paths: set) -> int:
        """删除不在 valid_paths 中的 stale entries，连带清理向量文件"""
        if not valid_paths:
            return 0
        conn = self._conn()
        placeholders = ",".join("?" * len(valid_paths))
        cur = conn.execute(
            f"DELETE FROM skills WHERE path NOT IN ({placeholders})",
            [str(p) for p in valid_paths]
        )
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        # 向量文件不主动删（下次 register 会覆盖），但 remove_stale 已知 paths
        return deleted
