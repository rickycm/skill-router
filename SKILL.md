---
name: skill-router
version: 2.0.0
description: Skill 语义路由系统 — 通过向量检索从技能池中找到最适合当前任务的 Skill 并自动调用，接管所有的skill调用
tags: [skill-router, vector-search, semantic-search, embedding]
author: Ricky
---

# Skill Router

基于阿里巴巴 SkillRouter 论文（arXiv:2603.22455）核心思想的两阶段检索系统。

## 系统架构

```
用户请求 → Query Embedding → 余弦相似度检索 → Top-K Skills
                ↓
         SQLite（元数据）+ NumPy（向量）
```

## 文件结构

```
skill-router/
├── SKILL.md                          # 本文档
├── requirements.txt                   # 依赖
├── skill_router/                     # Python 包
│   ├── __init__.py
│   ├── config.py                     # 配置加载
│   ├── embedding.py                  # Embedding 封装
│   ├── manifest.py                   # SKILL.md 解析
│   ├── registry.py                   # SQLite + NumPy 存储
│   ├── search.py                     # 检索逻辑
│   ├── router.py                     # 路由主入口
│   └── cli.py                        # CLI 工具
├── scripts/                          # 向后兼容脚本
│   ├── index_one.py
│   ├── index_skills.py
│   └── retrieve.py
└── data/
    ├── skill_embeddings.db           # SQLite（向量 + 元数据）
    └── vectors.npy                   # NumPy 向量矩阵
```

## CLI 命令

```bash
# 检索最匹配的 Skills
python3 -m skill_router.cli search "帮我搜索财经新闻"

# 列出所有已注册 Skills
python3 -m skill_router.cli list

# 安装单个 Skill
python3 -m skill_router.cli install ~/.openclaw/skills/byted-web-search

# 批量安装所有 Skills
python3 -m skill_router.cli install-all

# 卸载 Skill
python3 -m skill_router.cli uninstall <skill-name>
```

## Python SDK

```python
from skill_router import SkillRouter

# 初始化（自动从 OpenClaw 配置读取 API Key）
router = SkillRouter.create()

# 检索
results = router.route("帮我搜索财经新闻", top_k=5)
for r in results:
    print(f"{r.skill_name} {r.score:.4f} — {r.path}")

# 安装新 Skill
router.install("/path/to/skill")

# 列出所有
for s in router.list_skills():
    print(s["skill_name"])

# 卸载
router.uninstall("skill-name")
```

## 配置

支持两种配置方式：

**方式 1：`.env` 文件（推荐，打包分享时使用）**

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

**方式 2：复用 OpenClaw 配置**

自动从 `~/.openclaw/openclaw.json` 的 `memorySearch` 节点读取 API Key。

| 配置项 | .env 变量 | 值 |
|--------|-----------|-----|
| API 地址 | `OPENAI_BASE_URL` | `https://ai.gitee.com/v1` |
| 模型 | `OPENAI_MODEL` | `Qwen3-Embedding-0.6B` |
| 向量维度 | `OPENAI_DIMENSIONS` | 1024 |
| 返回数量 | `DEFAULT_TOP_K` | 5 |
| 最低阈值 | `MIN_SCORE_THRESHOLD` | 0.3 |

## 技术选型说明

| 设计决策 | 原因 |
|----------|------|
| SQLite + NumPy | 零额外依赖，< 1000 skills 性能足够 |
| 纯 Bi-Encoder | 当前规模无需 Cross-Encoder rerank |
| 复用 memorySearch API Key | 用户无需额外申请 |
| SKILL.md 作为 manifest | 与 OpenClaw skill 规范一致 |

## 安装指南

**新用户安装**：请阅读 [INSTALL.md](./INSTALL.md)，包含完整安装步骤、API Key 配置、故障排查。

---

## 未来扩展

- [ ] BM25 混合召回（skills > 100 后）
- [ ] Cross-Encoder rerank
- [ ] 增量更新（只重索引变化的 skill）
