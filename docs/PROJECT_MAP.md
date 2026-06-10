# 项目文件地图

本文档说明 `/root/cc/autowz` 主要文件和目录职责，帮助维护者/AI 快速定位修改位置。

## 根目录

| 路径 | 作用 |
|---|---|
| `README.md` | 面向用户/开发者的安装、运行、API 和流程说明。 |
| `CLAUDE.md` | 既有 Claude Code 项目说明。 |
| `AGENTS.md` | 面向 AI/自动化维护工具的上下文入口。 |
| `pyproject.toml` | Python 包、依赖、pytest、ruff 配置。 |
| `.env.example` | 环境变量示例。 |
| `.env` | 本地真实配置，敏感，默认不要读取/展示。 |
| `docker-compose.yml` | 本地 API + Redis + MySQL 环境。 |
| `image_providers.example.json` | 图片生成 provider 示例。 |
| `image_providers.json` | 真实图片 provider 配置，可能含 API key，敏感。 |
| `autowz.db` | 本地/历史数据库文件，默认不要读取。 |
| `uvicorn.log*` | 运行日志。 |

## `app/` 应用代码

| 路径 | 作用 |
|---|---|
| `app/main.py` | FastAPI app，lifespan 初始化数据库和调度器。 |
| `app/api/router.py` | 聚合并挂载 API 路由。 |
| `app/api/routes/health.py` | `GET /health`。 |
| `app/api/routes/articles.py` | 文章相关 API。 |
| `app/api/routes/scheduler.py` | 调度器相关 API。 |
| `app/core/config.py` | Pydantic Settings，从 `.env` 读取配置。 |
| `app/core/logging.py` | 日志配置。 |
| `app/models/schemas.py` | Pydantic 请求/响应模型。 |
| `app/tasks/scheduler.py` | APScheduler 定时任务定义。 |

## 数据库层 `app/db/`

| 路径 | 作用 |
|---|---|
| `app/db/engine.py` | SQLAlchemy engine、session factory、`get_db_session()`、`init_db()`。 |
| `app/db/models.py` | ORM 模型：`Topic`, `Article`, `WechatPublishRecord`。 |
| `app/db/crud.py` | 常用 CRUD 函数。 |

## 服务层 `app/services/`

| 路径 | 作用 |
|---|---|
| `app/services/pipeline.py` | `ArticlePipeline` 核心编排器。 |
| `app/services/content_length.py` | 中文字数统计、截断、追加“全文共 N 字”。 |
| `app/services/llm/client.py` | OpenAI 兼容 LLM 客户端、流式文本、JSON 提取。 |

### 采集模块 `app/services/collector/`

| 路径 | 作用 |
|---|---|
| `base.py` | `CollectedTopic`, `BaseCollector` 抽象。 |
| `weibo.py` | 微博热搜采集。 |
| `baidu.py` | 百度热搜采集。 |
| `manager.py` | 多采集器并发采集和标题相似去重。 |
| `search.py` | 新闻池和话题详情素材采集：天行 API、RSS、搜狗新闻搜索。 |

### 选题/写作/改写/风控

| 路径 | 作用 |
|---|---|
| `selector/service.py` | LLM 选题评分、分类优先级、fallback 选题。 |
| `writer/service.py` | LLM 写稿提示词、解析、fallback 文稿。 |
| `humanizer/service.py` | 人味化改写、扩写兜底、段落拆分、字数控制。 |
| `guard/blocklist.py` | 高/中风险词库和选题拦截函数。 |
| `guard/service.py` | 关键词快筛 + LLM 风控审核。 |

### 微信模块 `app/services/wechat/`

| 路径 | 作用 |
|---|---|
| `client.py` | 微信 API HTTP 客户端，统一 errcode 检查。 |
| `exceptions.py` | `WechatAPIError`。 |
| `token_service.py` | access_token 缓存、刷新、mock token。 |
| `material_service.py` | 上传永久封面素材和正文图片。 |
| `draft_service.py` | 创建图文草稿。 |
| `publish_service.py` | 提交发布、轮询发布状态。 |
| `service.py` | `WechatPublishOrchestrator` 发布总编排，处理 token 过期和降级。 |
| `cover_generator.py` | AI 生图 provider、封面下载/解析、Pillow 兜底封面。 |
| `mp_backend.py` | 微信公众平台后台内部接口，用 newwz 登录态拉已发表文章。 |
| `publish_sync.py` | 同步已发布文章 URL 到本地数据库。 |
| `reading_guide.py` | 构造底部“精彩文章导读”HTML。 |

## 脚本 `scripts/`

| 路径 | 作用 |
|---|---|
| `scripts/init_db.py` | 初始化数据库表。 |
| `scripts/generate_avatar.py` | 生成公众号头像。 |
| `scripts/test_image_providers.py` | 逐个测试图片 provider 生图能力。 |
| `scripts/update_ai_docs_index.py` | 生成/刷新 `docs/AUTO_PROJECT_INDEX.md`。 |

## 测试 `tests/`

| 路径 | 作用 |
|---|---|
| `tests/conftest.py` | FastAPI TestClient fixture。 |
| `tests/test_health.py` | `/` 和 `/health`。 |
| `tests/test_pipeline.py` | 文章预览流程 mock 测试。 |
| `tests/test_collector.py` | 采集器合并去重。 |
| `tests/test_selector.py` | fallback 选题优先级。 |
| `tests/test_guard.py` | 风控关键词。 |
| `tests/test_content_length.py` | 字数控制。 |

## 运行产物/资源目录

| 路径 | 说明 |
|---|---|
| `drafts/` | 生成的草稿 HTML/Markdown/封面图等运行产物。 |
| `tmp_image_test/`, `tmp_google_image_tests/` | 图片 provider 测试产物。 |
| `assets/avatars/` | 公众号头像图片。 |
| `data/` | 缓存数据，例如微信公众号 fakeid cache。 |

## 主要依赖关系

```text
app/main.py
  ├─ app/api/router.py
  ├─ app/db/engine.py
  └─ app/tasks/scheduler.py

app/api/routes/articles.py
  └─ app/services/pipeline.py
      ├─ collector/search.py
      ├─ selector/service.py
      ├─ writer/service.py
      ├─ humanizer/service.py
      ├─ guard/service.py + guard/blocklist.py
      ├─ wechat/cover_generator.py
      ├─ wechat/reading_guide.py
      ├─ wechat/service.py
      └─ db/crud.py + db/engine.py

wechat/service.py
  ├─ client.py
  ├─ token_service.py
  ├─ material_service.py
  ├─ draft_service.py
  └─ publish_service.py
```
