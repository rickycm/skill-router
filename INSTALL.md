# Skill Router 安装指南

> 本文档供 AI Agent 阅读，当用户请求「安装 skill-router」时，按此指南执行。

---

## 快速安装

```bash
# 1. 复制 skill 目录
cp -r skill-router/ ~/.openclaw/skills/

# 2. 安装依赖
pip install --break-system-packages ~/.openclaw/skills/skill-router

# 3. 初始化向量索引
cd ~/.openclaw/skills/skill-router
python3 -m skill_router install-all
```

---

## 配置 Embedding 模型

编辑 `skill-router/.env`（复制自 `.env.example`），选择其中一种：

### 方式 A：Gitee AI（推荐，免费）

```env
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=你的GiteeAI_API_Key
OPENAI_BASE_URL=https://ai.gitee.com/v1
OPENAI_MODEL=Qwen3-Embedding-0.6B
OPENAI_DIMENSIONS=1024
```

1. 注册 Gitee AI：https://ai.yuque.com
2. 获取 API Key 后填入 `.env`

### 方式 B：Ollama（本地，免费）

```env
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=nomic-embed-text
OLLAMA_DIMENSIONS=768
```

1. 安装 Ollama：https://ollama.com
2. 下载模型：`ollama pull nomic-embed-text`
3. 启动 Ollama 服务：`ollama serve`

### 方式 C：OpenAI / 其他兼容 API

```env
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=你的API_Key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=text-embedding-3-small
OPENAI_DIMENSIONS=1536
```

适用于 OpenAI、Azure OpenAI、SiliconFlow、TogetherAI 等兼容 OpenAI 格式的 API。

### 方式 D：复用 OpenClaw 已有配置

如果 `~/.openclaw/openclaw.json` 中已有 `memorySearch` 配置（包含可用 API Key），skill-router 会自动复用，无需手动配置。

---

## 安装到不同 AI Agent 平台

skill-router 是纯 Python 包，不依赖 OpenClaw，可安装到任何 AI Agent 平台。

### OpenClaw

```bash
pip install --break-system-packages ~/.openclaw/skills/skill-router
cd ~/.openclaw/skills/skill-router
python3 -m skill_router install-all
```

### Claude Code / OpenCode / Codex

```bash
pip install --break-system-packages ~/path/to/skill-router
cd ~/path/to/skill-router
python3 -m skill_router install-all
```

### 其他 Python 环境

```bash
pip install --break-system-packages /path/to/skill-router
python3 -m skill_router install-all
```

**通用前提：** Python 3.10+，pip

---

## 添加 Skills

将待管理的 skills 放入 `skill-router/.skills-pool/` 目录，然后重新索引：

```bash
# 放入新的 skill
cp -r /path/to/new-skill ~/.openclaw/skills/skill-router/.skills-pool/

# 重新索引（增量，已索引的会更新）
python3 -m skill_router install-all
```

---

## 使用方式

### CLI 命令

```bash
# 检索最匹配的 skills
python3 -m skill_router search "你的任务描述" --top-k 5

# 列出所有已注册 skills
python3 -m skill_router list

# 安装单个 skill
python3 -m skill_router install ~/.openclaw/skills/skill-router/.skills-pool/byted-web-search

# 卸载 skill
python3 -m skill_router uninstall <skill-name>

# 重新索引所有 skills
python3 -m skill_router install-all
```

### Python SDK

```python
from skill_router import SkillRouter

router = SkillRouter.create()

# 检索
results = router.route("帮我搜索财经新闻", top_k=5)
for r in results:
    print(f"{r.skill_name}  {r.score:.4f}  {r.path}")

# 安装新 skill
router.install("/path/to/new-skill")

# 列出所有
for s in router.list_skills():
    print(s["skill_name"])
```

---

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `No module named 'skill_router'` | 未安装包 | `pip install --break-system-packages ~/.openclaw/skills/skill-router` |
| `No module named 'httpx'` | 缺少依赖 | `pip install httpx numpy python-dotenv` |
| `找不到 embedding API key` | .env 未配置或 Key 无效 | 检查 `.env` 中的 API 配置 |
| `SKILL.md not found` | skill 目录缺少 SKILL.md | 确保目标 skill 有 SKILL.md 文件 |
| 检索返回空 | 向量数据库为空 | 先运行 `python3 -m skill_router install-all` |
| Ollama 连接失败 | 服务未启动 | 确保 `ollama serve` 在运行 |

---

## 目录结构

```
skill-router/                          # ← 整个目录复制到 ~/.openclaw/skills/
├── SKILL.md
├── INSTALL.md
├── requirements.txt
├── .env.example
├── .env                              # 填入你的 API Key
├── skill_router/                     # Python 包
│   ├── __init__.py
│   ├── __main__.py                  # 支持 python3 -m skill_router
│   ├── config.py                    # 配置加载
│   ├── embedding.py                  # Embedding 封装（OpenAI / Ollama）
│   ├── manifest.py                   # SKILL.md 解析
│   ├── registry.py                   # SQLite + NumPy 存储
│   ├── search.py                    # 检索逻辑
│   ├── router.py                    # 路由主入口
│   └── cli.py                       # CLI 工具
├── scripts/                          # 向后兼容脚本
└── .skills-pool/                     # ← 业务 skills 放这里
    ├── byted-web-search/
    ├── stock-analysis/
    └── ...（共 59 个）

data/                                  # ← 向量数据（自动生成）
├── skill_embeddings.db              # SQLite 元数据
└── vectors.npy                      # NumPy 向量矩阵
```

**注意：** `.skills-pool/` 带 `.` 前缀，OpenClaw 扫描时会忽略其中的 skills，确保 skill-router 是唯一被加载的入口。
