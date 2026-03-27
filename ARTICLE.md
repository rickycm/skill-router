# Skill Router：基于向量检索的 Agent 技能路由系统

> 本文结合阿里巴巴 SkillRouter 论文（arXiv:2603.22455）的研究成果，介绍 skill-router 项目的设计理念与实现方案。

---

## 背景问题：Agent 技能池的膨胀困境

2025-2026 年，AI Agent 生态经历了爆发式增长。从 Claude Code、Codex CLI 到各类开源 Agent 框架，社区贡献的技能（Skills/Tools/Plugins）数量已膨胀至数万个。GitHub 上的 awesome-openclaw-skills 仓库收录了上百个技能分类，涵盖代码审查、数据库迁移、API 集成、文档生成等方方面面。

然而，技能池的膨胀带来了一个关键问题：**如何从数万个候选技能中准确选出最适合当前任务的那一个？**

这个问题在学术界长期被忽视。现有的 benchmark（如 SkillBench、ToolBench）主要评估 Agent 在给定技能后能否正确使用，却没有研究"如何从大规模技能池中找到正确技能"这一上游问题。

---

## 核心发现：技能 body 才是决定性信号

阿里巴巴研究团队对 8 万规模技能池做了系统性实证研究，得出一个颠覆认知的结论：

> **技能名称和描述提供的区分度太低，真正决定选择准确率的是技能的完整实现代码（body）。**

### 实验数据佐证

| 检索方法 | name + description | name + description + body | 跌幅 |
|---------|-------------------|--------------------------|------|
| BM25 | 0% | 34.7% | 几乎归零 |
| Qwen3-Emb-0.6B | 22.7% | 58.7% | -36pp |
| Qwen3-Emb-8B | 30.7% | 64.0% | -33.3pp |

即便是 8B 参数的大模型，仅用名称和描述时也难以做出正确选择。而 0.6B 参数的模型使用完整文本时（58.7%），表现远超 8B 模型仅用名称描述的表现（30.7%）。

### 注意力分布分析

研究团队对交叉编码器的注意力权重进行了分区分析：

- **body 字段：91.7%** 的注意力权重
- **name 字段：7.3%**
- **description 字段：1.0%**

模型在判断技能是否适合当前任务时，几乎把全部注意力都放在了实现代码上。这印证了一个核心洞察：**技能路由系统必须能访问完整 body，仅靠名称+描述的路由方案从根本上就是受限的。**

---

## SkillRouter 论文的两阶段检索架构

基于上述发现，阿里团队提出了 **SkillRouter** ——一个两阶段检索-重排序流水线：

```
用户查询 → Embedding 编码 → Top-20 候选 → Cross-Encoder 重排序 → 最终排名
```

- **第一阶段（Bi-Encoder Retrieval）**：用微调的 Embedding 模型将查询和技能编码为向量，余弦相似度检索出 Top-20 候选
- **第二阶段（Cross-Encoder Reranking）**：用交叉编码器对 Top-20 候选进行精细排序

该流水线仅用 **1.2B 参数**（0.6B 编码器 + 0.6B 重排序器），在 8 万技能池上达到 **74.0%** 的平均 Hit@1，准确率超越 8B 参数的零样本基线。

---

## skill-router 项目：轻量级实现方案

本项目参考 SkillRouter 论文的核心思想，实现了 **适合个人/小团队使用** 的技能路由系统。

### 设计目标

| 目标 | 实现方式 |
|------|---------|
| 零额外依赖 | SQLite + NumPy，无需 Milvus 等向量数据库 |
| 低资源运行 | 纯 CPU 运行，可在笔记本上部署 |
| 完整 body 检索 | SKILL.md 解析 + 向量化，支持完整技能文本 |
| 增量更新 | 已索引技能自动更新，无需全量重建 |

### 系统架构

```
用户请求 → Query Embedding → 余弦相似度检索 → Top-K Skills
                ↓
         SQLite（元数据）+ NumPy（向量）
```

与论文的两阶段流水线不同，本项目采用 **单阶段向量检索** 方案，原因如下：

1. **规模适中**：个人/小团队技能池通常在数十到数百个，远小于论文研究的 8 万规模
2. **资源限制**：交叉编码器重排序需要更多计算资源，与"轻量级"目标冲突
3. **精度足够**：在中小规模下，单阶段检索的准确率已经足够使用

当技能池规模增长到数百个时，可考虑引入第二阶段重排序。

### 技术选型

| 设计决策 | 原因 |
|----------|------|
| SQLite + NumPy | 零额外依赖，零配置，零运维 |
| 纯 Bi-Encoder | <1000 skills 规模无需 Cross-Encoder rerank |
| 复用 memorySearch API | 用户无需额外申请 API Key |
| SKILL.md 作为 manifest | 与 OpenClaw skill 规范一致 |

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

# 安装新技能
router.install("/path/to/skill")

# 列出所有
for s in router.list_skills():
    print(s["skill_name"])
```

---

## 与论文方案的对比

| 特性 | SkillRouter 论文 | skill-router 项目 |
|------|-----------------|-----------------|
| 检索规模 | 8 万技能 | <1000 技能 |
| 流水线 | 两阶段（Retrieval + Rerank） | 单阶段向量检索 |
| 模型规模 | 1.2B（可扩展到 8B） | 依赖外部 Embedding API |
| 部署方式 | 本地模型 | API 调用或 Ollama |
| 存储 | 专用向量数据库 | SQLite + NumPy |
| 目标用户 | 企业级大规模部署 | 个人/小团队 |

本项目并非复现论文的完整方案，而是针对 **资源受限场景** 的实用化实现。对于更大规模的技能池，建议参考论文使用本地部署的 SR-Emb 和 SR-Rank 模型。

---

## 使用场景

- **个人 AI Agent**：管理数十到数百个自定义技能，快速定位所需工具
- **团队技能库**：统一管理团队贡献的技能，避免重复开发
- **技能市场**：构建技能发现和推荐系统
- **Agent 框架集成**：作为 Skill Selection 组件接入各类 Agent 框架

---

## 未来扩展方向

参考论文的消融实验，以下方向值得关注：

1. **Cross-Encoder 重排序**：当技能池规模超过 500 时，引入第二阶段重排序
2. **BM25 混合召回**：结合关键词检索，提升精确匹配能力
3. **增量索引**：只重索引变化的技能，而非全量重建
4. **本地 Embedding 模型**：使用 Ollama 或本地模型，减少 API 依赖

---

## 参考资源

- 论文： [SkillRouter: Efficient Skill Routing for LLM Agents](https://arxiv.org/abs/2603.22455)
- 项目仓库： [rickycm/skill-router](https://github.com/rickycm/skill-router)

---

## 总结

skill-router 项目将学术研究转化为实用工具，通过向量检索实现技能池的智能路由。核心设计理念与 SkillRouter 论文一致：**技能的完整实现文本才是决定选择准确率的关键**，而非业界普遍认为的名称和描述。

在个人/小团队使用场景下，本项目以极简的依赖和配置，提供足够准确的技能检索能力。对于更大规模的部署，论文提供了成熟的技术路径可供参考。
