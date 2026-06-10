# AI 快速上下文

## 项目是什么

`autowz` 是《今天怎么看》微信公众号自动发布系统：新闻采集 → LLM 选题 → LLM 写稿 → 人味化改写 → 风控审核 → 生成封面 → 创建草稿/发布到微信公众号。

## 新 AI 维护步骤

1. 读 `AGENTS.md`。
2. 按任务读 `docs/CHANGE_GUIDE.md` 对应章节。
3. 需要 API 信息时读 `docs/API_MAP.md`。
4. 需要数据结构时读 `docs/DATABASE.md`。
5. 只打开相关代码文件，不要扫描 `.env`、日志、草稿图、缓存、数据库等运行产物。
6. 修改后按 `docs/TESTING.md` 做最小验证。

## 最重要文件

| 文件 | 作用 |
|---|---|
| `app/main.py` | FastAPI 入口，启动 DB 和调度器。 |
| `app/services/pipeline.py` | 核心发文编排器。 |
| `app/core/config.py` | `.env` 配置。 |
| `app/db/models.py` | 数据库模型。 |
| `app/services/llm/client.py` | LLM 客户端。 |
| `app/services/selector/service.py` | 选题。 |
| `app/services/writer/service.py` | 写稿。 |
| `app/services/humanizer/service.py` | 人味化改写。 |
| `app/services/guard/blocklist.py` | 风控词库。 |
| `app/services/wechat/service.py` | 微信发布编排。 |
| `app/tasks/scheduler.py` | 定时任务。 |

## 核心链路

```text
API/定时任务 → ArticlePipeline → NewsCollector → TopicSelector → Writer → Humanizer → Guard → CoverGenerator → WechatPublishOrchestrator → MySQL
```

## 修改原则

- 小范围修改，不要无关重构。
- 不要泄漏 `.env`、API key、微信 token/cookie、数据库密码。
- 不要默认真实发布或触发高副作用 API。
- 修改配置要同步 `.env.example` 和文档。
- 修改数据库结构要考虑迁移，不能只依赖 `create_all()`。
