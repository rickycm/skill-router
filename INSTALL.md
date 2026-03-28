# Skill Router 安装指南

> 本文档供 AI Agent 阅读，当用户请求「安装 skill-router」时，按此指南执行。

---

## 快速安装

```bash
# 1. 复制 skill 目录
cp -r skill-router/ ~/.openclaw/skills/

# 2. 安装依赖（包含 Cisco Skill Scanner 安全扫描模块）
cd ~/.openclaw/skills/skill-router
pip install --break-system-packages .

# 3. 初始化向量索引
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

## Cisco Skill Scanner - 安全扫描配置

skill-router 集成了 Cisco Skill Scanner，在安装新 Skill 时自动进行安全扫描。

### 扫描模式

| 模式 | 说明 | 依赖 |
|------|------|------|
| **快速扫描** | 静态分析（YARA 规则、字节码、管道分析） | 无 |
| **深度扫描** | 静态 + LLM 语义分析 | 需要 LLM API 配置 |

### 配置深度扫描（可选）

编辑 `.env` 添加 LLM 配置：

```env
# LLM Provider: anthropic | openai | azure-openai | aws-bedrock | gcp-vertex | ollama | openrouter
SKILL_SCANNER_LLM_PROVIDER=anthropic
SKILL_SCANNER_LLM_API_KEY=your_api_key
SKILL_SCANNER_LLM_MODEL=claude-3-5-sonnet-20241022
```

### 安装后使用

```bash
# 安装单个 skill（交互式选择扫描模式）
python3 -m skill_router install /path/to/skill

# 强制使用快速扫描
python3 -m skill_router install /path/to/skill --scan-mode fast

# 跳过安全扫描（不推荐）
python3 -m skill_router install /path/to/skill --no-scan
```

---

## 安装到不同 AI Agent 平台

skill-router 是纯 Python 包，不依赖 OpenClaw，可安装到任何 AI Agent 平台。

### OpenClaw

```bash
cd ~/.openclaw/skills/skill-router
pip install --break-system-packages .
python3 -m skill_router install-all
```

### Claude Code / OpenCode / Codex

```bash
cd ~/path/to/skill-router
pip install --break-system-packages .
python3 -m skill_router install-all
```

### 其他 Python 环境

```bash
cd /path/to/skill-router
pip install --break-system-packages .
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
| `No module named 'skill_router'` | 未安装包 | `cd ~/.openclaw/skills/skill-router && pip install --break-system-packages .` |
| `No module named 'httpx'` | 缺少依赖 | `pip install httpx numpy python-dotenv` |
| `No module named 'skill_scanner'` | 缺少 skill-scanner | `pip install --break-system-packages .` 会自动安装 |
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
├── pyproject.toml                    # 项目配置（包含 Cisco Skill Scanner 依赖）
├── requirements.txt
├── .env.example
├── .env                              # 填入你的 API Key
├── skill_router/                     # Python 包
│   ├── _vendor/                    # 内置 Cisco Skill Scanner
│   │   └── skill_scanner/          # 安全扫描模块
│   ├── __init__.py
│   ├── __main__.py                  # 支持 python3 -m skill_router
│   ├── config.py                    # 配置加载
│   ├── embedding.py                  # Embedding 封装（OpenAI / Ollama）
│   ├── manifest.py                   # SKILL.md 解析
│   ├── registry.py                   # SQLite + NumPy 存储
│   ├── router.py                    # 路由主入口
│   ├── scanner.py                   # 安全扫描封装
│   └── cli.py                       # CLI 工具（含安全扫描集成）
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
