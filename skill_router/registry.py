#!/usr/bin/env python3
"""registry.py — Skill 注册表管理（SQLite + NumPy）"""

import sqlite3
import json
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict
from .manifest import read_manifest, SkillManifest
from .embedding import EmbeddingProvider


class SkillRegistry:
    def __init__(self, db_path: Path, vectors_path: Path, embedding: EmbeddingProvider):
        self.db_path = Path(db_path)
        self.vectors_path = Path(vectors_path)
        self.embedding = embedding
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
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
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_name ON skills(skill_name)")
        conn.commit()
        conn.close()

    def register(self, skill_path: str) -> int:
        """注册一个 Skill"""
        skill_path = Path(skill_path)
        manifest = read_manifest(skill_path)
        if not manifest:
            raise ValueError(f"SKILL.md not found in {skill_path}")

        # 计算 embedding
        combined_text = manifest.combined_text()
        vector = self.embedding.embed_one(combined_text)

        # 存入 SQLite
        conn = sqlite3.connect(str(self.db_path))
        import time
        indexed_at = str(int(time.time()))
        try:
            conn.execute("""
                INSERT INTO skills (skill_name, version, description, author, tags, path, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (manifest.name, manifest.version, manifest.description, manifest.author,
                  json.dumps(manifest.tags), str(skill_path), indexed_at))
            skill_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError:
            # 已存在，更新
            conn.execute("UPDATE skills SET version=?, description=?, author=?, tags=?, indexed_at=? WHERE path=?",
                        (manifest.version, manifest.description, manifest.author,
                         json.dumps(manifest.tags), indexed_at, str(skill_path)))
            skill_id = conn.execute("SELECT skill_id FROM skills WHERE path=?", (str(skill_path),)).fetchone()[0]
        conn.commit()
        conn.close()

        # 更新向量矩阵
        self._upsert_vector(skill_id, vector)
        return skill_id

    def _upsert_vector(self, skill_id: int, vector: List[float]):
        """更新向量矩阵（append 或 replace）"""
        vectors = self._load_vectors()
        arr = np.array(vector, dtype=np.float32)
        # 确保向量矩阵有足够的行
        if skill_id > len(vectors):
            vectors = np.vstack([vectors, np.zeros((skill_id - len(vectors), vectors.shape[1]), dtype=np.float32)]) if len(vectors) > 0 else arr.reshape(1, -1)
        if skill_id <= len(vectors):
            if skill_id == len(vectors) + 1:
                vectors = np.vstack([vectors, arr])
            else:
                vectors[skill_id - 1] = arr
        else:
            vectors = np.vstack([vectors, arr])
        np.save(self.vectors_path, vectors)

    def _load_vectors(self) -> np.ndarray:
        if not self.vectors_path.exists():
            return np.array([], dtype=np.float32).reshape(0, self.embedding.dimensions)
        v = np.load(self.vectors_path)
        if v.ndim == 1:
            return v.reshape(1, -1)
        return v

    def list_skills(self) -> List[Dict]:
        """列出所有已注册 skills"""
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT skill_id, skill_name, version, description, tags, path, indexed_at FROM skills ORDER BY skill_id").fetchall()
        conn.close()
        return [
            {"skill_id": r[0], "skill_name": r[1], "version": r[2], "description": r[3],
             "tags": json.loads(r[4]) if r[4] else [], "path": r[5], "indexed_at": r[6]}
            for r in rows
        ]

    def get_skill_by_id(self, skill_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT skill_id, skill_name, version, description, tags, path, indexed_at FROM skills WHERE skill_id=?",
                           (skill_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return {"skill_id": row[0], "skill_name": row[1], "version": row[2], "description": row[3],
                "tags": json.loads(row[4]) if row[4] else [], "path": row[5], "indexed_at": row[6]}

    def count(self) -> int:
        conn = sqlite3.connect(str(self.db_path))
        n = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        conn.close()
        return n

    def unregister(self, skill_name: str) -> bool:
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.execute("DELETE FROM skills WHERE skill_name=?", (skill_name,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def list_skill_paths(self) -> set:
        """获取所有已注册 skill 的路径集合"""
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT path FROM skills").fetchall()
        conn.close()
        return {Path(r[0]) for r in rows}

    def remove_stale(self, valid_paths: set) -> int:
        """删除不在 valid_paths 中的 stale entries，返回删除数量"""
        if not valid_paths:
            return 0
        conn = sqlite3.connect(str(self.db_path))
        placeholders = ",".join("?" * len(valid_paths))
        cur = conn.execute(
            f"DELETE FROM skills WHERE path NOT IN ({placeholders})",
            [str(p) for p in valid_paths]
        )
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        return deleted
