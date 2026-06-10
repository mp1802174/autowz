# AGENTS.md

本文件是给 AI 编程助手/自动化维护程序看的项目上下文入口。新模型接手本项目时，优先读取本文件，再按任务读取 `docs/CHANGE_GUIDE.md` 和 `docs/PROJECT_MAP.md` 的对应章节；不要一上来全量扫描数据库、日志、草稿图片、临时图片、缓存、`.env` 等文件。

## 项目一句话说明

`autowz` 是《今天怎么看》微信公众号自动发布系统：自动采集新闻/热点，使用 OpenAI 兼容 LLM 做选题、写稿、人味化改写和风控审核，生成封面图，创建微信公众号草稿，并可选择自动发布。

核心技术栈：

- FastAPI：HTTP API 与应用入口。
- APScheduler：定时采集、定时批量发文、同步已发布文章。
- SQLAlchemy + MySQL：保存话题、文章、发布记录。
- OpenAI compatible API：LLM 选题、写稿、改写、风控。
- httpx：异步 HTTP 请求。
- Pillow：封面图兜底生成/裁剪。
- pytest + ruff：测试与代码检查。

## 维护时优先阅读顺序

1. `AGENTS.md`：本文件，快速了解项目。
2. `docs/CHANGE_GUIDE.md`：按“要改什么功能”定位代码。
3. `docs/PROJECT_MAP.md`：文件/目录职责地图。
4. `docs/ARCHITECTURE.md`：请求链路、流水线、状态机。
5. `docs/API_MAP.md`：HTTP API 端点到代码映射。
6. `docs/CONFIGURATION.md`：`.env` 和 JSON 配置说明。
7. `docs/TESTING.md`：验证方式和禁止自动执行的高风险命令。

## 关键入口

| 入口 | 文件 | 说明 |
|---|---|---|
| FastAPI 应用 | `app/main.py` | 创建 app、lifespan 中初始化 DB 和调度器。 |
| API 路由聚合 | `app/api/router.py` | 挂载 health/articles/scheduler 路由。 |
| 文章 API | `app/api/routes/articles.py` | 预览、发布、采集、批次、查询。 |
| 调度 API | `app/api/routes/scheduler.py` | 查看/触发 APScheduler 任务。 |
| 核心编排器 | `app/services/pipeline.py` | ArticlePipeline：采集→选题→写作→改写→审核→发布。 |
| 定时任务 | `app/tasks/scheduler.py` | collect/batch/sync_published 定时任务。 |
| 配置 | `app/core/config.py` | Pydantic Settings，从 `.env` 读取。 |
| 数据库 | `app/db/models.py`, `app/db/crud.py`, `app/db/engine.py` | ORM、CRUD、engine/session。 |

## 不要默认读取/修改的文件和目录

这些通常包含敏感信息、运行产物或大文件，除非任务明确要求：

- `.env`, `.env.bak.*`, `image_providers.json`
- `autowz.db`, 其他 `*.db`
- `uvicorn.log`, `*.log`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`
- `.venv/`, `autowz.egg-info/`
- `drafts/`, `tmp_image_test/`, `tmp_google_image_tests/`, `tmp_test_cover.jpg`
- `assets/avatars/*.jpg` 等二进制图片
- `.claude/settings.local.json`
- `/root/cc/newwz/data/id_info.json` 等外部微信后台登录凭据

## 安全与隐私约定

- 不要输出或写入真实 API key、微信 AppSecret、后台 cookie/token、MySQL 密码。
- 文档示例只使用 `.env.example` 或脱敏值。
- 不要默认执行真实发布、自动发布、同步微信后台、生成真实封面图等有外部副作用的操作。
- 不要随意删除数据库、草稿、日志、图片产物。
- 修改风控、选题、发布逻辑要格外谨慎，避免绕过安全审核或导致公众号风险。

## 常用命令

```bash
# 安装/开发环境
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,db,worker]"

# 初始化数据库
python scripts/init_db.py

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 测试与检查
pytest tests/ -v
ruff check app tests scripts
python -m py_compile $(find app scripts tests -name '*.py' -not -path '*/__pycache__/*')

# 更新 AI 自动索引
python scripts/update_ai_docs_index.py
```

## 代码风格约定

- Python 3.11+，类型标注优先。
- 异步 I/O 使用 `async/await` 和 `httpx.AsyncClient`。
- 配置统一从 `get_settings()` 读取，不要在业务代码硬编码密钥。
- 数据库访问通过 `get_db_session()` + `app/db/crud.py` 封装，避免到处写重复查询。
- LLM 统一通过 `app/services/llm/client.py` 调用。
- 微信开放平台 API 统一通过 `app/services/wechat/*` 服务封装。
- 中文项目，注释和文档中文优先。
- Ruff 配置：line length 100，target Python 3.11。

## 最低验证建议

按修改范围选择：

```bash
pytest tests/ -v
ruff check app tests scripts
python -m py_compile $(find app scripts tests -name '*.py' -not -path '*/__pycache__/*')
curl http://localhost:8000/health
```

涉及真实外部服务的命令/API 调用需要用户明确确认。

## 常见任务定位

| 需求 | 优先文件 |
|---|---|
| 改 API 路由/参数/响应 | `app/api/routes/*.py`, `app/models/schemas.py` |
| 改完整发文流程 | `app/services/pipeline.py` |
| 改采集新闻/热点来源 | `app/services/collector/*.py` |
| 改 LLM 调用/重试/JSON 解析 | `app/services/llm/client.py` |
| 改选题逻辑 | `app/services/selector/service.py`, `app/services/guard/blocklist.py` |
| 改文章生成提示词 | `app/services/writer/service.py` |
| 改人味化/字数控制 | `app/services/humanizer/service.py`, `app/services/content_length.py` |
| 改风控词库/审核 | `app/services/guard/blocklist.py`, `app/services/guard/service.py` |
| 改微信草稿/发布 | `app/services/wechat/service.py`, `draft_service.py`, `publish_service.py`, `material_service.py` |
| 改封面图生成 | `app/services/wechat/cover_generator.py`, `image_providers.json`/`.example` |
| 改已发布文章同步 | `app/services/wechat/mp_backend.py`, `publish_sync.py`, `reading_guide.py` |
| 改定时任务 | `app/tasks/scheduler.py` |
| 改数据库结构 | `app/db/models.py`, `app/db/crud.py`, `scripts/init_db.py` |
| 改配置 | `app/core/config.py`, `.env.example`, `docs/CONFIGURATION.md` |
| 改测试 | `tests/*.py` |

更多细节见 `docs/CHANGE_GUIDE.md`。
