# Skill Router — 技术说明

> 基于阿里 SkillRouter 论文设计：技能 body 是决定选择准确率的关键信号（91.7% 注意力集中在 body）。

## 整体流程

```
安装阶段：
clawhub install xxx
    → post-install hook
    → 读取 SKILL.md + scripts/ + references/
    → Qwen3-Embedding API
    → LanceDB skill-embeddings 表

使用阶段：
用户任务
    → Qwen3-Embedding API（生成 query 向量）
    → LanceDB ANN 检索（cosine similarity，Top-5）
    → 返回结果
```

## 文件结构

```
~/.openclaw/skills/skill-router/
├── SKILL.md                         # 本文件
├── scripts/
│   ├── index_one.py               # 向量化单个 skill
│   ├── index_skills.py            # 批量向量化所有 skills
│   └── retrieve.py               # 检索最匹配的 skill
└── references/
    └── README.md
```

## 数据库

- **路径**：`~/.openclaw/memory/skill-embeddings.lance`
- **表名**：`skill_embeddings`
- **字段**：`vector[1024]`, `skill_id`, `skill_name`, `text_preview`

## Embedding 模型

- **API**：`https://ai.gitee.com/v1/embeddings`
- **模型**：`Qwen3-Embedding-0.6B`（1024 维）
- **API Key 来源**：从 `~/.openclaw/openclaw.json` 的 memorySearch 配置读取

## 使用方法

### 1. 首次安装后，批量向量化所有 skills
```bash
python3 ~/.openclaw/skills/skill-router/scripts/index_skills.py
```

### 2. 安装新 skill 后，向量化新 skill
```bash
python3 ~/.openclaw/skills/skill-router/scripts/index_one.py <skill-name>
```

### 3. 检索最匹配的 skill
```bash
python3 ~/.openclaw/skills/skill-router/scripts/retrieve.py "帮我搜索财经新闻"
```

### 4. 集成到 OpenClaw
通过 OpenClaw skill 调用，trigger 关键词：搜/查找、用哪个 skill、skill 选择、判断任务

## 当前状态

- [x] SKILL.md 已创建
- [x] index_one.py 已创建
- [x] index_skills.py 已创建
- [x] retrieve.py 已创建
- [ ] lancedb Python SDK 安装中（pip install）
- [ ] 首次批量向量化（待完成）
- [ ] 集成到 OpenClaw skill 系统

## 已知问题

- LanceDB Python SDK 安装较慢（需要编译 C++ 依赖）
- API Key 需要从 openclaw.json memorySearch 配置中读取（目前配置了 gitee.com）
