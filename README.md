# Skill Router

基于向量的 Skill 语义路由系统，通过向量检索从技能池中找到最适合当前任务的 Skill 并自动调用。

## 功能特性

- **语义检索**：基于 Embedding 向量相似度匹配，支持自然语言查询
- **两阶段检索**：Query Embedding → 余弦相似度检索 → Top-K Skills
- **多种 Embedding 支持**：OpenAI 兼容 API、Gitee AI、Ollama 本地模型
- **零额外依赖**：SQLite + NumPy 存储，< 1000 skills 性能足够
- **Python SDK + CLI**：灵活的编程和命令行使用方式
- **内置安全扫描**：集成 Cisco Skill Scanner，安装时自动进行安全扫描

## 系统要求

- Python 3.10+
- pip

## AI Agent 快速安装

适用于 OpenClaw / OpenCode / Claude Code / Codex 等 AI Agent 框架：

```
根据以下地址，安装和配置这个 skill：
https://github.com/rickycm/skill-router
```

详细安装说明请参考 [INSTALL.md](INSTALL.md)。

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
| `install <path>` | 安装单个 Skill（自动安全扫描） |
| `install-all` | 批量安装所有 Skills |
| `uninstall <name>` | 卸载 Skill |

### 安装参数

安装新 Skill 时会自动进行安全扫描：

| 参数 | 说明 |
|------|------|
| `--scan-mode fast` | 快速扫描（静态分析，无需额外配置） |
| `--scan-mode deep` | 深度扫描（静态+LLM，需配置 LLM API） |
| `--scan-mode skip` | 跳过扫描（不推荐） |
| `--no-scan` | 等同于 `--scan-mode skip` |

```bash
# 安装单个 Skill（交互式选择扫描模式）
python3 -m skill_router install /path/to/skill

# 使用快速扫描
python3 -m skill_router install /path/to/skill --scan-mode fast

# 跳过安全扫描
python3 -m skill_router install /path/to/skill --no-scan
```

## 安全扫描

Skill Router 内置 **Cisco Skill Scanner** 安全模块，在安装新 Skill 时自动进行安全扫描。

### 扫描模式

| 模式 | 说明 | 依赖 |
|------|------|------|
| **快速扫描** | 静态分析（YARA 规则、字节码、管道分析） | 无 |
| **深度扫描** | 静态 + LLM 语义分析 | 需要 LLM API 配置 |

### 检测威胁类型

- 提示注入 (Prompt Injection)
- 命令注入 (Command Injection)
- 数据泄露 (Data Exfiltration)
- 恶意代码 (Malware)
- 硬编码密钥 (Hardcoded Secrets)
- 混淆代码 (Obfuscation)
- 未授权工具使用 (Unauthorized Tool Use)
- 社会工程 (Social Engineering)
- 供应链攻击 (Supply Chain Attack)

### 配置深度扫描（可选）

编辑 `.env` 添加 LLM 配置：

```env
# LLM Provider: anthropic | openai | azure-openai | aws-bedrock | gcp-vertex | ollama | openrouter
SKILL_SCANNER_LLM_PROVIDER=anthropic
SKILL_SCANNER_LLM_API_KEY=your_api_key
SKILL_SCANNER_LLM_MODEL=claude-3-5-sonnet-20241022
```

## 项目结构

```
skill-router/
├── skill_router/              # Python 包
│   ├── _vendor/               # 内置安全扫描模块
│   │   └── skill_scanner/     # Cisco Skill Scanner
│   ├── config.py             # 配置加载
│   ├── embedding.py          # Embedding 封装
│   ├── manifest.py           # SKILL.md 解析
│   ├── registry.py           # SQLite + NumPy 存储
│   ├── scanner.py            # 安全扫描封装
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
| 内置安全扫描 | 安装时自动检测威胁，保障安全 |

## License

MIT
