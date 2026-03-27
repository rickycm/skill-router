#!/usr/bin/env python3
"""retrieve.py — 检索最匹配的 skill（调用模块版本）"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill_router"))

from skill_router import SkillRouter

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检索匹配的 Skills")
    parser.add_argument("query", help="用户任务描述")
    parser.add_argument("--top-k", type=int, default=5, help="返回数量（默认5）")
    args = parser.parse_args()

    router = SkillRouter.create()
    results = router.route(args.query, top_k=args.top_k)

    print(f"\n📊 找到 {len(results)} 个匹配的 Skills\n")
    print("═" * 60)
    for i, r in enumerate(results, 1):
        bar = "█" * int(r.score * 20)
        print(f"\n[{i}] {r.skill_name}  {bar} {r.score:.4f}")
        if r.description:
            print(f"    📝 {r.description[:80]}")
        print(f"    📂 {r.path}")
    if not results:
        print("没有找到匹配的 Skills")
