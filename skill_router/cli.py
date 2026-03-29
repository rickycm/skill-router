#!/usr/bin/env python3
"""cli.py — Skill Router CLI 工具"""

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_router import SkillRouter
from skill_router.config import _skills_pool_dir, _skills_install_dir, _skill_dir

# Skills 资源池路径（被检索但不被 OpenClaw 扫描）
SKILLS_POOL = _skills_pool_dir()
SKILLS_INSTALL_DIR = _skills_install_dir()
SKILL_ROUTER_DIR = _skill_dir()
EXCLUDE = {"clawhub", "node_modules", ".git", "__pycache__", ".DS_Store"}


def _show_first_run_banner():
    """首次安装时显示 Cisco Skill Scanner 集成提示"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   🔒 Cisco Skill Scanner 集成                                        ║
║                                                                      ║
║   Skill Router 现已集成 Cisco Skill Scanner 安全模块，               ║
║   可在安装新 Skill 时进行安全扫描，检测:                              ║
║                                                                      ║
║     • 提示注入 (Prompt Injection)                                     ║
║     • 命令注入 (Command Injection)                                   ║
║     • 数据泄露 (Data Exfiltration)                                   ║
║     • 恶意代码 (Malware)                                             ║
║     • 硬编码密钥 (Hardcoded Secrets)                                 ║
║                                                                      ║
║   扫描模式:                                                          ║
║     [1] 快速扫描 - 静态分析，无需额外配置                            ║
║     [2] 深度扫描 - 静态+LLM，需要配置 LLM API Key                    ║
║     [3] 跳过扫描 - 不推荐，仅在信任来源时使用                         ║
║                                                                      ║
║   深度扫描配置说明（可选）:                                           ║
║     SKILL_SCANNER_LLM_PROVIDER=anthropic  # 或 openai/azure-bedrock  ║
║     SKILL_SCANNER_LLM_API_KEY=your_key                               ║
║     SKILL_SCANNER_LLM_MODEL=claude-3-5-sonnet-20241022               ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
    """)


def _prompt_scan_mode() -> str:
    """交互式选择扫描模式"""
    print("\n🔒 选择安全扫描模式:")
    print("  [1] 快速扫描 (静态分析) - 快速安全")
    print("  [2] 深度扫描 (静态+LLM) - 更全面，需配置 LLM API")
    print("  [3] 跳过扫描 (不推荐)")
    print()
    while True:
        choice = input("请选择 [1/2/3] (默认: 1): ").strip() or "1"
        if choice == "1":
            return "fast"
        elif choice == "2":
            return "deep"
        elif choice == "3":
            return "skip"
        print("无效选择，请重新输入")


def _display_scan_summary(result) -> None:
    """显示扫描摘要（安装成功后）"""
    if result is None:
        return
    status = "✅ 安全" if result.is_safe else "⚠️ 发现问题"
    print(f"\n🔍 扫描结果: {status}")
    print(f"   最大严重性: {result.max_severity.value}")
    print(f"   发现项: {len(result.findings)}")


def _display_full_report(result) -> None:
    """显示完整扫描报告（扫描失败时）"""
    try:
        from skill_router._vendor.skill_scanner.core.reporters import TableReporter
        reporter = TableReporter()
        print("\n" + reporter.generate_report(result))
    except Exception:
        # Fallback: 简单输出
        print("\n" + "=" * 60)
        print(f"🚨 安全威胁报告: {result.skill_name}")
        print("=" * 60)
        for f in result.findings:
            print(f"\n[{f.severity.value}] {f.title}")
            print(f"  规则: {f.rule_id}")
            print(f"  文件: {f.file_path or 'N/A'}")
            if f.description:
                print(f"  描述: {f.description[:200]}")
            if f.remediation:
                print(f"  修复: {f.remediation}")


def cmd_init(args):
    """初始化：扫描并迁移已安装的 skills 到管理目录"""
    import shutil

    router = SkillRouter.create()

    if not SKILLS_INSTALL_DIR.exists():
        print(f"❌ Skills 安装目录不存在: {SKILLS_INSTALL_DIR}")
        sys.exit(1)

    # 扫描安装目录中的 skills（包含 symlink，因为 symlink 也可能指向真实目录）
    all_skills = {
        d: d / "SKILL.md"
        for d in SKILLS_INSTALL_DIR.iterdir()
        if (d.is_dir() or d.is_symlink()) and d != SKILL_ROUTER_DIR and d.name not in EXCLUDE
    }

    # 只保留有 SKILL.md 的目录
    existing_skills = {
        name: path for name, path in all_skills.items() if path.exists()
    }

    if not existing_skills:
        print(f"📂 在 {SKILLS_INSTALL_DIR} 中未发现其他 Skills")
        print(f"💡 首次使用，请使用 'python3 -m skill_router install <path>' 安装新 Skill")
        sys.exit(0)

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   🔄 Skill Router 初始化                                            ║
║                                                                      ║
║   发现 {len(existing_skills)} 个已安装的 Skills，准备迁移到管理目录...              ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"📂 发现以下 Skills:\n")
    for i, (name, path) in enumerate(sorted(existing_skills.items()), 1):
        print(f"  [{i}] {name}")

    print(f"\n→ 迁移到: {SKILLS_POOL}")
    print(f"→ Skill Router 目录不会被迁移\n")

    # 确定扫描模式
    scan_mode = getattr(args, "scan_mode", "prompt")
    if scan_mode == "prompt":
        scan_mode = _prompt_scan_mode()

    # 确保 .skills-pool 存在
    SKILLS_POOL.mkdir(parents=True, exist_ok=True)

    print(f"🔒 扫描模式: {scan_mode}\n")

    success, skipped, failed, blocked = 0, 0, 0, 0
    blocked_results = []

    for name, skill_path in sorted(existing_skills.items()):
        dest = SKILLS_POOL / name

        # 如果目标已存在，跳过
        if dest.exists():
            print(f"  ⏭ {name}（已存在于 .skills-pool/）")
            skipped += 1
            continue

        # 移动到 .skills-pool（真实移动，不使用 symlink）
        # shutil.move() 对 symlink 只移动链接文件本身，需要分情况处理
        try:
            if skill_path.is_symlink():
                # Symlink: 复制真实内容到目标，删除原始 symlink
                real_target = skill_path.resolve()
                shutil.copytree(str(real_target), str(dest), symlinks=False)
                skill_path.unlink()  # 删除 symlink 本身
            else:
                # 真实目录: 直接移动
                shutil.move(str(skill_path), str(dest))
            print(f"  ✅ {name} → 已迁移")
        except Exception as e:
            print(f"  ❌ {name}: 迁移失败 - {e}")
            failed += 1
            continue

        # 注册并扫描
        try:
            _, scan_result = router.install(str(dest), scan_mode=scan_mode)
            success += 1
        except Exception as e:
            if hasattr(e, "scan_result") and e.scan_result is not None:
                print(f"  🔒 {name} - 安全扫描阻止")
                blocked_results.append((name, e.scan_result, dest, skill_path))
                blocked += 1
            else:
                print(f"  ❌ {name}: {e}")
                failed += 1

    print(f"\n{'=' * 60}")
    print(f"迁移完成：{success} 成功，{skipped} 跳过，{blocked} 被阻止，{failed} 失败")

    if blocked_results:
        print(f"\n🚨 被阻止的 Skills ({len(blocked_results)}):")
        for name, result, dest, original_path in blocked_results:
            # 回滚：移回原始位置
            try:
                if dest.is_symlink():
                    real_target = dest.resolve()
                    shutil.copytree(str(real_target), str(original_path), symlinks=False)
                    shutil.rmtree(str(dest))
                else:
                    shutil.move(str(dest), str(original_path))
                print(f"  🔒 {name}: 已回滚（移回原始位置）")
            except Exception as e:
                print(f"  🔒 {name}: 回滚失败，请手动处理 {dest} -> {original_path}: {e}")
            findings = result.findings
            high_count = sum(1 for f in findings if f.severity.value in ("HIGH", "CRITICAL"))
            print(f"     {high_count} 高危发现 - {result.max_severity.value}")
        print(f"\n💡 使用 'python3 -m skill_router install --scan-mode skip' 强制安装")

    if success > 0:
        print(f"\n✅ 初始化完成！当前共有 {router.count()} 个 Skills 已索引")
        print(f"💡 使用 'python3 -m skill_router list' 查看所有 Skills")


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
    skills = router.list_all_skills()
    print(f"\n📦 共 {len(skills)} 个 Skills\n")
    print("═" * 60)
    for s in skills:
        status_icon = {"ready": "✅", "pending": "⏳", "failed": "❌"}.get(s.get("status"), "?")
        print(f"  {status_icon} {s['skill_name']}  (v{s['version'] or '?'})  — {s['description'][:50] or ''}  [{s.get('status', '?')}]")


def cmd_install(args):
    skill_path = Path(args.path).resolve()
    if not skill_path.exists():
        print(f"❌ 路径不存在: {skill_path}")
        sys.exit(1)
    if not (skill_path / "SKILL.md").exists():
        print(f"❌ SKILL.md 不存在: {skill_path}")
        sys.exit(1)

    router = SkillRouter.create()

    # 首次安装显示欢迎横幅
    if router.count() == 0:
        _show_first_run_banner()

    # 确定扫描模式
    scan_mode = getattr(args, "scan_mode", "prompt")
    if scan_mode == "prompt":
        scan_mode = _prompt_scan_mode()

    try:
        skill_id, scan_result = router.install(str(skill_path), scan_mode=scan_mode)
        print(f"✅ 已安装并索引: {skill_path.name} (id={skill_id})")
        _display_scan_summary(scan_result)
    except Exception as e:
        # 检查是否是安全扫描失败
        if hasattr(e, "scan_result") and e.scan_result is not None:
            print(f"\n❌ 安全扫描未通过，拒绝安装:")
            _display_full_report(e.scan_result)
            print("\n💡 如需强制安装，可使用: --scan-mode skip")
            sys.exit(1)
        else:
            print(f"❌ 安装失败: {e}")
            sys.exit(1)


def cmd_install_all(args):
    router = SkillRouter.create()
    if not SKILLS_POOL.exists():
        print(f"❌ Skills 资源池不存在: {SKILLS_POOL}")
        print("请先创建 .skills-pool 目录并放入 skills")
        sys.exit(1)

    # 首次安装显示欢迎横幅
    if router.count() == 0:
        _show_first_run_banner()

    skills = [d for d in os.listdir(SKILLS_POOL)
              if os.path.isdir(SKILLS_POOL / d) and d not in EXCLUDE]

    # 批量安装默认使用快速扫描
    scan_mode = getattr(args, "scan_mode", "fast")
    if scan_mode == "prompt":
        print("批量安装模式: 使用快速扫描 (static only)")
        scan_mode = "fast"

    print(f"📂 扫描路径: {SKILLS_POOL}")
    print(f"🔒 扫描模式: {scan_mode}")
    print(f"找到 {len(skills)} 个 skills，准备批量索引...\n")

    success, skipped, failed, blocked = 0, 0, 0, 0
    blocked_results = []

    for name in sorted(skills):
        sp = SKILLS_POOL / name
        if not (sp / "SKILL.md").exists():
            print(f"  ⏭ {name}（无 SKILL.md）")
            skipped += 1
            continue
        try:
            _, scan_result = router.install(str(sp), scan_mode=scan_mode)
            print(f"  ✅ {name}")
            success += 1
        except Exception as e:
            if hasattr(e, "scan_result") and e.scan_result is not None:
                print(f"  🔒 {name} - 扫描阻止 (threats detected)")
                blocked_results.append((name, e.scan_result))
                blocked += 1
            else:
                print(f"  ❌ {name}: {e}")
                failed += 1

    print(f"\n完成：{success} 成功，{skipped} 跳过，{blocked} 被阻止，{failed} 失败")

    if blocked_results:
        print(f"\n{'=' * 60}")
        print(f"被阻止的 Skills ({len(blocked_results)}):")
        for name, result in blocked_results:
            findings = result.findings
            high_count = sum(1 for f in findings if f.severity.value in ("HIGH", "CRITICAL"))
            print(f"  🔒 {name}: {high_count} 高危发现 - {result.max_severity.value}")
        print(f"\n使用 'skill-scanner scan <path> --format table' 查看详细信息")


def cmd_uninstall(args):
    router = SkillRouter.create()
    ok = router.uninstall(args.name)
    if ok:
        print(f"✅ 已卸载: {args.name}")
    else:
        print(f"❌ 未找到: {args.name}")


def cmd_status(args):
    router = SkillRouter.create()
    counts = router.count_all()
    print(f"""
📊 Skill Router 索引状态

  ✅ Ready:   {counts['ready']}
  ⏳ Pending: {counts['pending']}
  ❌ Failed:  {counts['failed']}
  ─────────────
  总计:       {counts['total']}
""")
    if counts["pending"] > 0:
        print("正在处理的 Skills:")
        for s in router.list_all_skills():
            if s.get("status") == "pending":
                print(f"  ⏳ {s['skill_name']} — {s.get('path', '')}")
    if counts["failed"] > 0:
        print("\n失败的 Skills:")
        for s in router.list_all_skills():
            if s.get("status") == "failed":
                print(f"  ❌ {s['skill_name']} — {s.get('path', '')}")


def main():
    parser = argparse.ArgumentParser(description="Skill Router CLI")
    sub = parser.add_subparsers()

    p_search = sub.add_parser("search", help="检索匹配的 Skills")
    p_search.add_argument("query", help="查询任务描述")
    p_search.add_argument("--top-k", type=int, default=5, help="返回数量（默认5）")
    p_search.set_defaults(fn=cmd_search)

    p_list = sub.add_parser("list", help="列出所有已注册 Skills")
    p_list.set_defaults(fn=cmd_list)

    p_init = sub.add_parser("init", help="初始化：扫描并迁移已安装的 Skills")
    p_init.add_argument("--scan-mode", choices=["fast", "deep", "skip", "prompt"],
                        default="prompt", help="安全扫描模式（默认: prompt）")
    p_init.set_defaults(fn=cmd_init)

    p_install = sub.add_parser("install", help="安装单个 Skill")
    p_install.add_argument("path", help="Skill 目录路径")
    p_install.add_argument("--scan-mode", choices=["fast", "deep", "skip", "prompt"],
                            default="prompt", help="安全扫描模式（默认: prompt）")
    p_install.add_argument("--no-scan", action="store_true",
                            help="跳过安全扫描（不推荐）")
    p_install.set_defaults(fn=cmd_install)

    p_install_all = sub.add_parser("install-all", help="批量安装所有 Skills")
    p_install_all.add_argument("--scan-mode", choices=["fast", "deep", "skip"],
                               default="fast", help="安全扫描模式（默认: fast）")
    p_install_all.add_argument("--no-scan", action="store_true",
                              help="跳过安全扫描（不推荐）")
    p_install_all.set_defaults(fn=cmd_install_all)

    p_uninstall = sub.add_parser("uninstall", help="卸载 Skill")
    p_uninstall.add_argument("name", help="Skill 名称")
    p_uninstall.set_defaults(fn=cmd_uninstall)

    p_status = sub.add_parser("status", help="查看索引状态（pending/ready/failed）")
    p_status.set_defaults(fn=cmd_status)

    args = parser.parse_args()

    # 处理 --no-scan 标志
    if hasattr(args, "no_scan") and args.no_scan:
        args.scan_mode = "skip"

    if hasattr(args, "fn"):
        args.fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
