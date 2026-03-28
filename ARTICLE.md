# Skill Router：基于向量检索的 Agent 技能路由系统

---

## 背景问题：Agent 技能池的膨胀困境

2025-2026 年，AI Agent 生态经历了爆发式增长。从 Claude Code、Codex CLI 到各类开源 Agent 框架，社区贡献的技能（Skills/Tools/Plugins）数量已膨胀至数万个。GitHub 上的 awesome-openclaw-skills 仓库收录了上百个技能分类，涵盖代码审查、数据库迁移、API 集成、文档生成等方方面面。

然而，技能池的膨胀带来了三个关键问题：

1. **选择困难**：如何从数万个候选技能中准确选出最适合当前任务的那一个？
2. **安全隐患**：来源不明的技能可能包含恶意代码、提示注入或数据泄露风险
3. **降智风险**：技能越多，上下文越膨胀，模型反而容易"变笨"

**Skill Router 完美解决这三个问题。**

---

## AI Agent 快速安装

适用于 OpenClaw / OpenCode / Claude Code / Codex 等 AI Agent 框架：

```
根据以下地址，安装和配置这个 skill：
https://github.com/rickycm/skill-router
```

---

## 核心发现：技能 body 才是决定性信号

研究表明，技能的名称和描述提供的区分度太低，真正决定选择准确率的是技能的完整实现代码（body）。

### 为什么名称和描述不够用？

社区技能仓库存在严重的**功能重叠**问题。比如搜索"git"相关的操作，你可能会找到几十个功能相似但实现细节不同的技能：有的用 shell 脚本，有的用 Python，有的支持 PR 自动合并，有的只做 commit 检查。名字和描述可能都很像，但真正的差异藏在实现代码里。

在数万个功能重叠的技能池中，光靠"pdf-merger"这样一个名字和一句"合并 PDF 文件的工具"这样的描述，根本无法区分几十个功能相似的技能。真正的区分信号藏在 body 里——具体的实现逻辑、使用的库、参数配置、错误处理方式等。

### 注意力分布揭示的真相

研究表明，模型在判断技能是否适合当前任务时：

- **body 字段：91.7%** 的注意力权重
- **name 字段：7.3%**
- **description 字段：1.0%**

模型先读懂代码（body），再对照名称做匹配，最后回到代码做决定。这说明：**技能路由系统必须能访问完整 body，仅靠名称+描述的路由方案从根本上就是受限的。**

---

## 三大核心特性

### 1. 精准路由 — 节省 tokens，用好 Skill

Skill Router 采用 **基于 Embedding 的向量检索**，在路由阶段访问完整的技能文本（SKILL.md + 实现代码），确保选出的技能是真正适合当前任务的。

- **节省 tokens**：只加载最相关的那一个技能，而非把所有技能名称都塞进上下文
- **用好 Skill**：基于完整 body 语义匹配，而非简单的关键词匹配
- **渐进式披露**：名称描述常驻上下文 → 选中后才加载完整指令 → 按需调用脚本

### 2. 安全扫描 — 安装即检测，安心使用

Skill Router 内置 **Cisco Skill Scanner** 安全扫描模块，在安装新技能时自动进行多维度安全检测：

| 威胁类型 | 说明 |
|----------|------|
| 提示注入 (Prompt Injection) | 检测恶意指令注入 |
| 命令注入 (Command Injection) | 检测危险系统命令 |
| 数据泄露 (Data Exfiltration) | 检测敏感信息外传 |
| 恶意代码 (Malware) | 检测木马、后门等恶意程序 |
| 硬编码密钥 (Hardcoded Secrets) | 检测 API Key 等敏感凭证 |
| 混淆代码 (Obfuscation) | 检测隐蔽恶意逻辑 |

**快速扫描**：静态分析（YARA 规则、字节码、管道分析），无需额外配置
**深度扫描**：静态 + LLM 语义分析，需配置 LLM API

### 3. 持续可用 — 技能再多不降智

随着技能池膨胀，传统方案面临"上下文爆炸"问题：

```
❌ 技能 10 个：上下文够用，AI 表现正常
❌ 技能 100 个：上下文开始膨胀，AI 响应变慢
❌ 技能 500 个：上下文爆炸，AI 严重降智
```

**Skill Router 的精准路由确保无论技能池如何膨胀，上下文占用始终可控：**

- 只索引最相关的 Top-K 技能
- 名称描述轻量常驻，详细指令按需加载
- 向量检索 O(1) 空间复杂度，不随技能数量线性增长

---

## 系统架构

```
用户请求 → Query Embedding → 余弦相似度检索 → Top-K Skills
                ↓
         SQLite（元数据）+ NumPy（向量）
```

### 设计目标

| 目标 | 实现方式 |
|------|---------|
| 零额外依赖 | SQLite + NumPy，无需 Milvus 等向量数据库 |
| 低资源运行 | 纯 CPU 运行，可在笔记本上部署 |
| 完整 body 检索 | SKILL.md 解析 + 向量化，支持完整技能文本 |
| 增量更新 | 已索引技能自动更新，无需全量重建 |
| 内置安全扫描 | Cisco Skill Scanner，开箱即用 |

### 技术选型

| 设计决策 | 原因 |
|----------|------|
| SQLite + NumPy | 零额外依赖，零配置，零运维 |
| 纯 Bi-Encoder | <1000 skills 规模无需 Cross-Encoder rerank |
| SKILL.md 作为 manifest | 与 OpenClaw skill 规范一致 |
| 内置安全扫描 | 安装即检测，无需第三方工具 |

---

## 功能特性

### 语义检索

基于 Embedding 向量相似度匹配，支持自然语言查询。例如：

```bash
$ python3 -m skill_router search "帮我搜索财经新闻"

akshare-stock    0.8472  ─  A股量化分析工具
agent-reach      0.7923  ─  搜索和读取17个平台内容
byted-web-search 0.7561  ─  字节搜索工具
```

系统返回与查询语义最相近的技能，按相似度排序。

### 渐进式披露设计

系统采用渐进式披露（Progressive Disclosure）设计模式：

- **第一层**：技能的名称和描述常驻上下文
- **第二层**：被选中后才加载完整的 SKILL.md 指令
- **第三层**：按需调用脚本和资源文件

### 安装时安全扫描

```bash
# 安装技能，自动触发安全扫描
python3 -m skill_router install /path/to/skill

# 选择扫描模式
--scan-mode fast   # 快速扫描（默认）
--scan-mode deep   # 深度扫描（需要 LLM API）
--no-scan          # 跳过扫描（不推荐）
```

发现威胁时阻止安装并显示完整报告：

```
❌ 安全扫描未通过，拒绝安装:
   [HIGH] 提示注入攻击检测
   规则: LLM_PROMPT_INJECTION
   文件: SKILL.md
   描述: 检测到可疑的指令覆盖模式
```

### 多 Embedding 提供者支持

```python
# Gitee AI（默认）
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://ai.gitee.com/v1

# OpenAI
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Ollama（本地）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=nomic-embed-text
```

### Python SDK

```python
from skill_router import SkillRouter

router = SkillRouter.create()

# 检索
results = router.route("帮我搜索财经新闻", top_k=5)
for r in results:
    print(f"{r.skill_name} {r.score:.4f} — {r.path}")

# 安装新技能（自动安全扫描）
router.install("/path/to/skill")

# 列出所有
for s in router.list_skills():
    print(s["skill_name"])

# 卸载技能
router.uninstall("skill-name")
```

### CLI 命令

| 命令 | 说明 |
|------|------|
| `search <query>` | 检索最匹配的 Skills |
| `list` | 列出所有已注册 Skills |
| `install <path>` | 安装单个 Skill（自动安全扫描） |
| `install-all` | 批量安装所有 Skills |
| `uninstall <name>` | 卸载 Skill |

---

## 使用场景

- **个人 AI Agent**：管理数十到数百个自定义技能，快速定位所需工具
- **团队技能库**：统一管理团队贡献的技能，避免重复开发 + 安全审核
- **技能市场**：构建技能发现、推荐和安全审核一体化平台
- **Agent 框架集成**：作为 Skill Selection + Security 组件接入各类 Agent 框架

---

## 性能特点

- **准确率高**：利用完整技能文本（body）进行向量检索，避免仅依赖名称和描述的局限性
- **响应快速**：SQLite + NumPy 的轻量级存储方案，纯 CPU 推理，亚毫秒级检索
- **资源占用低**：无需 GPU，支持在笔记本等端侧设备部署
- **隐私友好**：支持本地 Ollama 模型，查询和技能数据不外传
- **安全可信**：内置 Cisco Skill Scanner，安装即检测

---

## 未来扩展方向

1. **Cross-Encoder 重排序**：当技能池规模超过 500 时，引入第二阶段重排序提升准确率
2. **BM25 混合召回**：结合关键词检索，提升精确匹配能力
3. **增量索引**：只重索引变化的技能，而非全量重建
4. **本地 Embedding 模型**：使用 Ollama 或其他本地模型，减少 API 依赖

---

## 参考资源

- 项目仓库： [rickycm/skill-router](https://github.com/rickycm/skill-router)

---

## 总结

Skill Router 通过向量检索实现技能池的智能路由，**完美解决技能囤积带来的三大问题**：

| 问题 | 传统方案 | Skill Router |
|------|----------|--------------|
| 选择困难 | 靠名称猜 | 精准向量匹配 |
| 安全隐患 | 靠信任 | 安装即扫描 |
| 降智风险 | 无解 | Top-K 按需加载 |

核心设计理念：**技能的完整实现文本是决定选择准确率的关键**，而非业界普遍认为的名称和描述。

在个人/小团队使用场景下，本项目以极简的依赖和配置（SQLite + NumPy），提供基于完整 body 检索的技能路由能力，同时内置安全扫描确保技能来源可信。用户无需额外申请 API Key，也无需搭建复杂的向量数据库服务，即可在笔记本等端侧设备上部署使用。
