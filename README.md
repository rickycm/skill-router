# Skill Router

基于向量的 Skill 语义路由系统，通过向量检索从技能池中找到最适合当前任务的 Skill 并自动调用。

## 功能特性

- **语义检索**：基于 Embedding 向量相似度匹配，支持自然语言查询
- **两阶段检索**：Query Embedding → 余弦相似度检索 → Top-K Skills
- **多种 Embedding 支持**：OpenAI 兼容 API、Gitee AI、Ollama 本地模型
- **零额外依赖**：SQLite + NumPy 存储，< 1000 skills 性能足够
- **Python SDK + CLI**：灵活的编程和命令行使用方式

## 系统要求

- Python 3.10+
- pip

## 快速开始

### 1. 安装

```bash
pip install --break-system-packages .
```

### 2. 配置

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
```

支持的 Embedding 提供者：

| 提供者 | 配置 |
|--------|------|
| Gitee AI（推荐） | `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://ai.gitee.com/v1` |
| OpenAI | `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.openai.com/v1` |
| Ollama（本地） | `OLLAMA_BASE_URL=http://localhost:11434` + `OLLAMA_MODEL=nomic-embed-text` |

### 3. 初始化索引

```bash
python3 -m skill_router install-all
```

### 4. 使用

**CLI 检索：**

```bash
python3 -m skill_router search "帮我搜索财经新闻" --top-k 5
```

**Python SDK：**

```python
from skill_router import SkillRouter

router = SkillRouter.create()

# 检索最匹配的 Skills
results = router.route("帮我搜索财经新闻", top_k=5)
for r in results:
    print(f"{r.skill_name} {r.score:.4f} — {r.path}")
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `search <query>` | 检索最匹配的 Skills |
| `list` | 列出所有已注册 Skills |
| `install <path>` | 安装单个 Skill |
| `install-all` | 批量安装所有 Skills |
| `uninstall <name>` | 卸载 Skill |

## 项目结构

```
skill-router/
├── skill_router/              # Python 包
│   ├── config.py             # 配置加载
│   ├── embedding.py          # Embedding 封装
│   ├── manifest.py           # SKILL.md 解析
│   ├── registry.py           # SQLite + NumPy 存储
│   ├── search.py             # 检索逻辑
│   ├── router.py             # 路由主入口
│   └── cli.py                # CLI 工具
├── scripts/                   # 向后兼容脚本
├── .skills-pool/             # Skill 存放目录
└── data/                      # 向量数据（自动生成）
    ├── skill_embeddings.db
    └── vectors.npy
```

## 技术选型

| 设计决策 | 原因 |
|----------|------|
| SQLite + NumPy | 零额外依赖，零配置 |
| 纯 Bi-Encoder | 当前规模无需 Cross-Encoder rerank |
| SKILL.md 作为 manifest | 与 OpenClaw skill 规范一致 |

## License

MIT
