#!/usr/bin/env python3
"""index_one.py — 向量化单个 skill（调用模块版本）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill_router"))

from skill_router import SkillRouter

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 index_one.py <skill-name-or-path>")
        sys.exit(1)
    skill_path = sys.argv[1]
    # 如果只给 name，补全路径
    if not Path(skill_path).exists():
        skill_path = str(Path.home() / ".openclaw/skills" / skill_path)
    router = SkillRouter.create()
    skill_id = router.install(skill_path)
    print(f"✅ 已索引: {Path(skill_path).name} (id={skill_id})")
