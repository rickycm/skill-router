#!/usr/bin/env python3
"""cli.py — Skill Router CLI 工具"""

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_router import SkillRouter
from skill_router.config import _skills_pool_dir

# Skills 资源池路径（被检索但不被 OpenClaw 扫描）
SKILLS_POOL = _skills_pool_dir()
EXCLUDE = {"clawhub", "node_modules", ".git", "__pycache__", ".DS_Store"}


def cmd_search(args):
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


def cmd_list(args):
    router = SkillRouter.create()
    skills = router.list_skills()
    print(f"\n📦 共 {len(skills)} 个已注册的 Skills\n")
    print("═" * 60)
    for s in skills:
        print(f"  • {s['skill_name']}  (v{s['version'] or '?'})  — {s['description'][:50] or ''}")


def cmd_install(args):
    skill_path = Path(args.path).resolve()
    if not skill_path.exists():
        print(f"❌ 路径不存在: {skill_path}")
        sys.exit(1)
    if not (skill_path / "SKILL.md").exists():
        print(f"❌ SKILL.md 不存在: {skill_path}")
        sys.exit(1)

    router = SkillRouter.create()
    skill_id = router.install(str(skill_path))
    print(f"✅ 已安装并索引: {skill_path.name} (id={skill_id})")


def cmd_install_all(args):
    router = SkillRouter.create()
    if not SKILLS_POOL.exists():
        print(f"❌ Skills 资源池不存在: {SKILLS_POOL}")
        print("请先创建 .skills-pool 目录并放入 skills")
        sys.exit(1)
    skills = [d for d in os.listdir(SKILLS_POOL)
              if os.path.isdir(SKILLS_POOL / d) and d not in EXCLUDE]
    print(f"📂 扫描路径: {SKILLS_POOL}")
    print(f"找到 {len(skills)} 个 skills，准备批量索引...\n")
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


def cmd_uninstall(args):
    router = SkillRouter.create()
    ok = router.uninstall(args.name)
    if ok:
        print(f"✅ 已卸载: {args.name}")
    else:
        print(f"❌ 未找到: {args.name}")


def main():
    parser = argparse.ArgumentParser(description="Skill Router CLI")
    sub = parser.add_subparsers()

    p_search = sub.add_parser("search", help="检索匹配的 Skills")
    p_search.add_argument("query", help="查询任务描述")
    p_search.add_argument("--top-k", type=int, default=5, help="返回数量（默认5）")
    p_search.set_defaults(fn=cmd_search)

    p_list = sub.add_parser("list", help="列出所有已注册 Skills")
    p_list.set_defaults(fn=cmd_list)

    p_install = sub.add_parser("install", help="安装单个 Skill")
    p_install.add_argument("path", help="Skill 目录路径")
    p_install.set_defaults(fn=cmd_install)

    p_install_all = sub.add_parser("install-all", help="批量安装所有 Skills")
    p_install_all.set_defaults(fn=cmd_install_all)

    p_uninstall = sub.add_parser("uninstall", help="卸载 Skill")
    p_uninstall.add_argument("name", help="Skill 名称")
    p_uninstall.set_defaults(fn=cmd_uninstall)

    args = parser.parse_args()
    if hasattr(args, "fn"):
        args.fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
