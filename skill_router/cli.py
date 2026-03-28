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
