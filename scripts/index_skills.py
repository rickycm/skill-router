#!/usr/bin/env python3
"""index_skills.py — 批量向量化所有 skills（扫描 .skills-pool 目录）"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill_router"))

from skill_router import SkillRouter
from skill_router.config import _skills_pool_dir

SKILLS_POOL = _skills_pool_dir()
EXCLUDE = {"clawhub", "node_modules", ".git", "__pycache__", ".DS_Store"}

if __name__ == "__main__":
    if not SKILLS_POOL.exists():
        print(f"❌ Skills 资源池不存在: {SKILLS_POOL}")
        print("请确认 skills 已迁移到该目录")
        sys.exit(1)

    skills = [d for d in os.listdir(SKILLS_POOL)
              if os.path.isdir(SKILLS_POOL / d) and d not in EXCLUDE]
    print(f"📂 扫描路径: {SKILLS_POOL}")
    print(f"找到 {len(skills)} 个 skills，准备批量索引...\n")
    router = SkillRouter.create()
    success, skipped, failed = 0, 0, 0
    for name in sorted(skills):
        sp = SKILLS_POOL / name
        if not (sp / "SKILL.md").exists():
            print(f"  ⏭ {name}（无 SKILL.md）")
            skipped += 1
            continue
        try:
            router.install(str(sp))
            print(f"  ✅ {name}")
            success += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
    print(f"\n完成：{success} 成功，{skipped} 跳过，{failed} 失败")
