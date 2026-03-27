#!/usr/bin/env python3
"""manifest.py — Skill Manifest 读取"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class SkillManifest:
    name: str
    description: str
    version: str
    author: str
    tags: list
    body: str
    path: str

    def combined_text(self) -> str:
        """拼接完整文本供 embedding"""
        tags_str = ", ".join(self.tags) if self.tags else ""
        return f"""SKILL_NAME: {self.name}
SKILL_DESCRIPTION: {self.description}
SKILL_TAGS: {tags_str}
SKILL_BODY: {self.body}"""


def read_manifest(skill_path: Path) -> Optional[SkillManifest]:
    """读取 skill 目录下的 SKILL.md"""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    raw = skill_md.read_text(encoding="utf-8")
    return _parse_markdown(raw, str(skill_path))


def _parse_markdown(text: str, path: str) -> SkillManifest:
    """解析 SKILL.md"""
    lines = text.split("\n")
    name = _extract_field(lines, "name") or Path(path).name
    description = _extract_field(lines, "description") or ""
    version = _extract_field(lines, "version") or ""
    author = _extract_field(lines, "author") or ""

    tags_str = _extract_field(lines, "tags") or ""
    tags = [t.strip().strip("\"'[]") for t in re.split(r"[,，]", tags_str) if t.strip()]

    # body = SKILL.md 完整内容
    body = text

    return SkillManifest(
        name=name,
        description=description,
        version=version,
        author=author,
        tags=tags,
        body=body,
        path=path,
    )


def _extract_field(lines: list, field: str) -> str:
    """从 markdown 中提取 field"""
    import re
    for line in lines:
        line = line.strip()
        # Pattern 1: "field: value" (markdown inline)
        m = re.match(rf"^{re.escape(field)}\s*:\s*(.+)$", line)
        if m:
            return m.group(1).strip()
        # Pattern 2: YAML frontmatter "{field: value}"
        m = re.match(rf"^\s*{re.escape(field)}\s*:\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    return ""
