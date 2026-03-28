# scanner.py — Skill Scanner 安全扫描封装层
"""
集成 Cisco Skill Scanner，在 Skill 安装前进行安全扫描。
支持快速扫描（静态分析）和深度扫描（静态+LLM）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

try:
    from skill_router._vendor.skill_scanner.core.scanner import SkillScanner
    from skill_router._vendor.skill_scanner.core.analyzer_factory import build_core_analyzers, build_analyzers
    from skill_router._vendor.skill_scanner.core.scan_policy import ScanPolicy
    from skill_router._vendor.skill_scanner.core.models import ScanResult
    _SCANNER_AVAILABLE = True
except ImportError:
    _SCANNER_AVAILABLE = False


class SecurityScanFailed(Exception):
    """安全扫描发现威胁时抛出"""

    def __init__(self, scan_result: ScanResult):
        super().__init__(f"Security threats detected: {len(scan_result.findings)} findings")
        self.scan_result = scan_result


def is_scanner_available() -> bool:
    """检查 skill-scanner 是否已安装"""
    return _SCANNER_AVAILABLE


def pre_install_scan(
    skill_path: str | Path,
    mode: Literal["fast", "deep", "skip"],
) -> Optional[ScanResult]:
    """
    在 Skill 安装前执行安全扫描。

    Args:
        skill_path: Skill 目录路径
        mode: 扫描模式
            - "fast": 静态分析（无需 LLM 配置）
            - "deep": 静态+LLM 深度分析（需要 LLM API 配置）
            - "skip": 跳过扫描

    Returns:
        ScanResult 对象，扫描通过时返回

    Raises:
        SecurityScanFailed: 发现威胁时抛出
    """
    if not _SCANNER_AVAILABLE:
        print("⚠️  skill-scanner 未安装，跳过安全扫描")
        return None

    if mode == "skip":
        return None

    skill_path = Path(skill_path)
    if not skill_path.exists():
        raise ValueError(f"Skill 路径不存在: {skill_path}")

    policy = ScanPolicy.default()

    if mode == "fast":
        analyzers = build_core_analyzers(policy)
    elif mode == "deep":
        api_key = os.getenv("SKILL_SCANNER_LLM_API_KEY")
        if not api_key:
            print("⚠️  深度扫描需要配置 SKILL_SCANNER_LLM_API_KEY，回退到快速扫描")
            analyzers = build_core_analyzers(policy)
        else:
            analyzers = build_analyzers(
                policy,
                use_llm=True,
                llm_provider=os.getenv("SKILL_SCANNER_LLM_PROVIDER", "anthropic"),
                llm_api_key=api_key,
                llm_model=os.getenv("SKILL_SCANNER_LLM_MODEL"),
                llm_base_url=os.getenv("SKILL_SCANNER_LLM_BASE_URL") or None,
                llm_api_version=os.getenv("SKILL_SCANNER_LLM_API_VERSION") or None,
                aws_region=os.getenv("SKILL_SCANNER_AWS_REGION") or None,
                aws_profile=os.getenv("SKILL_SCANNER_AWS_PROFILE") or None,
                aws_session_token=os.getenv("SKILL_SCANNER_AWS_SESSION_TOKEN") or None,
            )
    else:
        raise ValueError(f"Unknown scan mode: {mode}")

    scanner = SkillScanner(analyzers=analyzers, policy=policy)
    result = scanner.scan_skill(skill_path)

    # 发现威胁则阻止安装
    if not result.is_safe:
        raise SecurityScanFailed(scan_result=result)

    return result
