# ADR-001：建立 AI 维护文档体系

## 状态

已采用。

## 背景

本项目涉及 FastAPI、LLM、微信公众号、MySQL、定时任务、图片生成等多个模块，并包含 `.env`、日志、草稿图片、后台 cookie、数据库等敏感或大体积运行产物。不同 AI 模型接手维护时，如果每次全量扫描，成本高且容易误读或泄漏敏感内容。

## 决策

建立面向 AI 的维护文档体系：

- `AGENTS.md`
- `docs/AI_CONTEXT.md`
- `docs/PROJECT_MAP.md`
- `docs/CHANGE_GUIDE.md`
- `docs/API_MAP.md`
- `docs/ARCHITECTURE.md`
- `docs/CONFIGURATION.md`
- `docs/DATABASE.md`
- `docs/TESTING.md`
- `docs/AUTO_PROJECT_INDEX.md`

并提供 `scripts/update_ai_docs_index.py` 用于刷新自动索引。

## 后果

优点：

- 新 AI 可快速定位修改点。
- 降低无关扫描和敏感信息泄漏风险。
- 常见维护需求可按文档直接映射到代码文件。

代价：

- 代码结构、API、配置、数据库变化后需要同步更新文档。
- 自动索引需要在结构变化后手动刷新。
