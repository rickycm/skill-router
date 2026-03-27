#!/usr/bin/env python3
"""migrate_to_v2.py — 从旧格式迁移到新格式（SQLite + NumPy 分离）"""

import sqlite3
import numpy as np
from pathlib import Path

OLD_DB = Path(__file__).resolve().parent.parent / "data" / "skill_embeddings.db"
NEW_DB = OLD_DB
NEW_VECTORS = Path(__file__).resolve().parent.parent / "data" / "vectors.npy"


def migrate():
    conn = sqlite3.connect(str(OLD_DB))
    cols = [c[1] for c in conn.execute("PRAGMA table_info(skills)").fetchall()]
    print(f"旧表列: {cols}")

    # 旧格式: skill_id, skill_name, text_preview, indexed_at, vector
    # 新格式: skill_id, skill_name, version, description, author, tags, path, indexed_at (vector 移入 .npy)
    has_vector_blob = "vector" in cols

    if not has_vector_blob:
        print("已是新格式或无向量数据，无需迁移")
        conn.close()
        return

    print("检测到旧格式，开始迁移...")
    rows = conn.execute("SELECT skill_id, skill_name, text_preview, indexed_at, vector FROM skills").fetchall()
    print(f"找到 {len(rows)} 条记录")

    # 重建新表结构
    conn.execute("DROP TABLE IF EXISTS skills")
    conn.execute("""
        CREATE TABLE skills (
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

    vectors_list = []
    for skill_id, skill_name, text_preview, indexed_at, vector_blob in rows:
        # 从 text_preview 提取 description（取前300字作为 description）
        description = text_preview[:300] if text_preview else ""
        conn.execute("""
            INSERT INTO skills (skill_name, version, description, author, tags, path, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (skill_name, "", description, "", "[]", skill_name, indexed_at))

        if vector_blob:
            vec = np.frombuffer(vector_blob, dtype=np.float32)
            vectors_list.append(vec)
        else:
            vectors_list.append(np.zeros(1024, dtype=np.float32))
        print(f"  ✅ {skill_name}")

    conn.commit()
    conn.close()

    if vectors_list:
        vectors_arr = np.vstack(vectors_list)
        np.save(NEW_VECTORS, vectors_arr)
        print(f"\n✅ 迁移完成：{len(vectors_list)} 条记录，向量矩阵 {vectors_arr.shape}")

    # 验证
    conn2 = sqlite3.connect(str(OLD_DB))
    count = conn2.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    conn2.close()
    v = np.load(NEW_VECTORS)
    print(f"验证：SQLite {count} 条，vectors.npy {v.shape}")


if __name__ == "__main__":
    migrate()
