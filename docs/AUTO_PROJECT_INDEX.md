# 自动/半自动项目索引

生成时间：2026-05-28T16:57:33

> 由 `scripts/update_ai_docs_index.py` 生成。已排除 `.env`、真实 provider 配置、日志、数据库、缓存、草稿图片、虚拟环境等。

## 核心 Python 模块摘要

| 文件 | 顶层定义 | 顶层导入 |
|---|---|---|
| `app/main.py` | async def lifespan; async def root | app, contextlib, fastapi, logging |
| `app/api/router.py` | - | app, fastapi |
| `app/api/routes/articles.py` | async def preview_article; async def publish_article; async def collect_topics; async def list_today_topics; async def get_article; async def run_batch | app, datetime, fastapi |
| `app/api/routes/scheduler.py` | async def scheduler_status; async def trigger_job | app, fastapi |
| `app/api/routes/health.py` | async def health | fastapi |
| `app/core/config.py` | class Settings; def get_settings | functools, pydantic, pydantic_settings |
| `app/core/logging.py` | def setup_logging | app, logging, sys |
| `app/db/engine.py` | def get_engine; def get_session_factory; def get_db_session; def init_db | app, contextlib, sqlalchemy |
| `app/db/models.py` | class Base; class Topic; class Article; class WechatPublishRecord | datetime, sqlalchemy |
| `app/db/crud.py` | def save_topic; def save_topic_upsert; def get_topics_by_date; def get_selected_topics; def get_recent_selected_topics; def update_topic_status; def save_article; def get_article_by_id; def update_article_status; def get_articles_by_status; def save_publish_record; def update_publish_record; def get_pending_publish_records; def get_random_published_articles | app, datetime, sqlalchemy |
| `app/models/schemas.py` | class TopicCandidate; class ArticlePreviewRequest; class ArticlePreviewResponse; class PublishArticleRequest; class PublishArticleResponse; class WechatArticlePayload; class WechatPublishResult | pydantic, typing |
| `app/services/pipeline.py` | def _normalize_title; def _is_similar_to_any; class ArticlePipeline | app, datetime, logging, re |
| `app/services/collector/search.py` | class NewsItem; class SearchResult; class TopicContext; def _normalize_title; class NewsCollector | app, dataclasses, feedparser, httpx, logging, re |
| `app/services/collector/manager.py` | class CollectorManager | app, asyncio, difflib, logging |
| `app/services/selector/service.py` | class TopicSelectorService | app, logging |
| `app/services/writer/service.py` | class WriterService | app, logging, markdown |
| `app/services/humanizer/service.py` | class HumanizerService | app, logging, markdown |
| `app/services/guard/blocklist.py` | def _normalize; def match_high_risk; def match_medium_risk; def is_topic_blocked; def is_topic_risky | - |
| `app/services/guard/service.py` | class GuardService | app, logging |
| `app/services/llm/client.py` | class LLMClient; def get_llm_client | app, asyncio, functools, json, logging, openai |
| `app/services/wechat/service.py` | class WechatPublishOrchestrator | app, logging |
| `app/services/wechat/cover_generator.py` | async def generate_cover_async; def generate_cover; async def _generate_ai_cover; async def _generate_via_chat_completion; def _build_image_providers; def _redact_url; async def _generate_with_provider; async def _do_call_provider; async def _generate_via_images_generation; async def _image_bytes_from_generation_response; async def _image_bytes_from_chat_response; async def _image_bytes_from_candidate; async def _download_or_decode_image; def _decode_image_text; def _raise_for_status_with_body; def _clean_content_excerpt; def _prepare_output_path; def _crop_to_cover_ratio; def _generate_text_cover; def _load_font; def _draw_wrapped_text | PIL, app, base64, httpx, io, json, logging, pathlib, re, tempfile, typing |
| `app/services/wechat/mp_backend.py` | class MpBackendError; class MpBackendAuthExpired; class WechatMpBackend | datetime, httpx, json, logging, pathlib |
| `app/services/wechat/publish_sync.py` | async def sync_published_articles | app, logging |
| `app/tasks/scheduler.py` | def get_scheduler; async def _job_collect; async def _job_batch; async def _job_sync_published; def init_scheduler; def shutdown_scheduler; def get_scheduler_status | apscheduler, logging |

## 路由装饰器索引

| 文件 | 路由 |
|---|---|
| `app/main.py` | app.get('/', tags=['root']) -> root |
| `app/api/routes/articles.py` | router.post('/preview', response_model=ArticlePreviewResponse) -> preview_article; router.post('/publish', response_model=PublishArticleResponse) -> publish_article; router.post('/collect') -> collect_topics; router.get('/topics') -> list_today_topics; router.get('/{article_id}') -> get_article; router.post('/batch/{batch_type}') -> run_batch |
| `app/api/routes/scheduler.py` | router.get('/status') -> scheduler_status; router.post('/trigger/{job_id}') -> trigger_job |
| `app/api/routes/health.py` | router.get('/health') -> health |

## 核心文件列表（已排除运行产物）

```text
.env.example
.gitignore
AGENTS.md
CLAUDE.md
README.md
app/__init__.py
app/api/__init__.py
app/api/router.py
app/api/routes/__init__.py
app/api/routes/articles.py
app/api/routes/health.py
app/api/routes/scheduler.py
app/core/__init__.py
app/core/config.py
app/core/logging.py
app/db/__init__.py
app/db/crud.py
app/db/engine.py
app/db/models.py
app/main.py
app/models/__init__.py
app/models/schemas.py
app/services/__init__.py
app/services/collector/__init__.py
app/services/collector/baidu.py
app/services/collector/base.py
app/services/collector/manager.py
app/services/collector/search.py
app/services/collector/weibo.py
app/services/content_length.py
app/services/guard/__init__.py
app/services/guard/blocklist.py
app/services/guard/service.py
app/services/humanizer/__init__.py
app/services/humanizer/service.py
app/services/llm/__init__.py
app/services/llm/client.py
app/services/pipeline.py
app/services/selector/__init__.py
app/services/selector/service.py
app/services/wechat/__init__.py
app/services/wechat/client.py
app/services/wechat/cover_generator.py
app/services/wechat/draft_service.py
app/services/wechat/exceptions.py
app/services/wechat/material_service.py
app/services/wechat/mp_backend.py
app/services/wechat/publish_service.py
app/services/wechat/publish_sync.py
app/services/wechat/reading_guide.py
app/services/wechat/service.py
app/services/wechat/token_service.py
app/services/writer/__init__.py
app/services/writer/service.py
app/tasks/__init__.py
app/tasks/scheduler.py
docker-compose.yml
docs/AI_CONTEXT.md
docs/API_MAP.md
docs/ARCHITECTURE.md
docs/AUTO_PROJECT_INDEX.md
docs/CHANGE_GUIDE.md
docs/CONFIGURATION.md
docs/DATABASE.md
docs/PROJECT_MAP.md
docs/TESTING.md
docs/adr/001-ai-maintenance-docs.md
docs/开发文档-今天怎么看-微信公众号自动发布系统.md
image_providers.example.json
pyproject.toml
scripts/generate_avatar.py
scripts/init_db.py
scripts/test_image_providers.py
scripts/update_ai_docs_index.py
tests/conftest.py
tests/test_collector.py
tests/test_content_length.py
tests/test_guard.py
tests/test_health.py
tests/test_pipeline.py
tests/test_selector.py
```

## 主要命令

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
python scripts/init_db.py
pytest tests/ -v
ruff check app tests scripts
python scripts/update_ai_docs_index.py
```
