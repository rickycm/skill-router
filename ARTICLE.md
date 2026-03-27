# Skill Router：基于向量检索的 Agent 技能路由系统

---

## 背景问题：Agent 技能池的膨胀困境

2025-2026 年，AI Agent 生态经历了爆发式增长。从 Claude Code、Codex CLI 到各类开源 Agent 框架，社区贡献的技能（Skills/Tools/Plugins）数量已膨胀至数万个。GitHub 上的 awesome-openclaw-skills 仓库收录了上百个技能分类，涵盖代码审查、数据库迁移、API 集成、文档生成等方方面面。

然而，技能池的膨胀带来了一个关键问题：**如何从数万个候选技能中准确选出最适合当前任务的那一个？**

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

## 系统架构

skill-router 采用 **基于 Embedding 的向量检索** 方案：

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

### 渐进式披露设计

系统采用渐进式披露（Progressive Disclosure）设计模式：

- **第一层**：技能的名称和描述常驻上下文
- **第二层**：被选中后才加载完整的 SKILL.md 指令
- **第三层**：按需调用脚本和资源文件

在路由阶段，系统访问完整的技能文本（SKILL.md + 实现代码），确保选出的技能是真正适合当前任务的。

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

# 卸载技能
router.uninstall("skill-name")
```

### CLI 命令

| 命令 | 说明 |
|------|------|
| `search <query>` | 检索最匹配的 Skills |
| `list` | 列出所有已注册 Skills |
| `install <path>` | 安装单个 Skill |
| `install-all` | 批量安装所有 Skills |
| `uninstall <name>` | 卸载 Skill |

---

## 使用场景

- **个人 AI Agent**：管理数十到数百个自定义技能，快速定位所需工具
- **团队技能库**：统一管理团队贡献的技能，避免重复开发
- **技能市场**：构建技能发现和推荐系统
- **Agent 框架集成**：作为 Skill Selection 组件接入各类 Agent 框架

---

## 性能特点

- **准确率高**：利用完整技能文本（body）进行向量检索，避免仅依赖名称和描述的局限性
- **响应快速**：SQLite + NumPy 的轻量级存储方案，纯 CPU 推理，亚毫秒级检索
- **资源占用低**：无需 GPU，支持在笔记本等端侧设备部署
- **隐私友好**：支持本地 Ollama 模型，查询和技能数据不外传

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

skill-router 通过向量检索实现技能池的智能路由。核心设计理念是：**技能的完整实现文本是决定选择准确率的关键**，而非业界普遍认为的名称和描述。

在个人/小团队使用场景下，本项目以极简的依赖和配置（SQLite + NumPy），提供基于完整 body 检索的技能路由能力。用户无需额外申请 API Key（可复用 memorySearch 配置），也无需搭建复杂的向量数据库服务，即可在笔记本等端侧设备上部署使用。
