# API 地图

默认 API 前缀由 `.env` 的 `API_PREFIX` 控制，默认 `/api/v1`。`/health` 和 `/` 不带此前缀。

## 路由挂载关系

```text
app/main.py
  app.include_router(api_router)

app/api/router.py
  include health_router                  → /health
  include articles_router + API_PREFIX   → /api/v1/articles/...
  include scheduler_router + API_PREFIX  → /api/v1/scheduler/...
```

## 根和健康检查

| 方法 | 路径 | 函数 | 文件 | 说明 |
|---|---|---|---|---|
| GET | `/` | `root()` | `app/main.py` | 返回 app/env/message。 |
| GET | `/health` | `health()` | `app/api/routes/health.py` | 返回 `{"status":"ok"}`。 |

## 文章 API

文件：`app/api/routes/articles.py`  
router：`APIRouter(prefix="/articles", tags=["articles"])`

| 方法 | 路径 | 函数 | 请求模型 | 响应模型/返回 | 说明 |
|---|---|---|---|---|---|
| POST | `/api/v1/articles/preview` | `preview_article()` | `ArticlePreviewRequest` | `ArticlePreviewResponse` | 搜索素材并生成预览，不发布。 |
| POST | `/api/v1/articles/publish` | `publish_article()` | `PublishArticleRequest` | `PublishArticleResponse` | 完整发布流程，失败时部分 ValueError 转 400。 |
| POST | `/api/v1/articles/collect` | `collect_topics()` | 无 | `{count, topics}` | 手动采集新闻池并入库。 |
| GET | `/api/v1/articles/topics` | `list_today_topics()` | 无 | list | 查询今日 topics。 |
| GET | `/api/v1/articles/{article_id}` | `get_article()` | path int | dict | 查询文章详情，不存在返回 404。 |
| POST | `/api/v1/articles/batch/{batch_type}` | `run_batch()` | path str | `{batch_type, results}` | 手动触发 morning/noon/evening 批次。 |

相关 Pydantic 模型在 `app/models/schemas.py`：

- `ArticlePreviewRequest`
- `ArticlePreviewResponse`
- `PublishArticleRequest`
- `PublishArticleResponse`
- `WechatArticlePayload`
- `WechatPublishResult`

## 调度器 API

文件：`app/api/routes/scheduler.py`  
router：`APIRouter(prefix="/scheduler", tags=["scheduler"])`

| 方法 | 路径 | 函数 | 说明 |
|---|---|---|---|
| GET | `/api/v1/scheduler/status` | `scheduler_status()` | 查看所有定时任务状态。 |
| POST | `/api/v1/scheduler/trigger/{job_id}` | `trigger_job()` | 触发指定 APScheduler job，不存在返回 404。 |

当前 job id 定义在 `app/tasks/scheduler.py`：

| job id | 函数 | 触发时间 | 说明 |
|---|---|---|---|
| `collect_hot_topics` | `_job_collect()` | 每 30 分钟 | 采集新闻池。 |
| `morning_batch` | `_job_batch("morning", 2, "finance")` | 07:05 | 经济类 2 篇。 |
| `noon_batch` | `_job_batch("noon", 2, "entertainment")` | 12:05 | 娱乐类 2 篇。 |
| `evening_batch` | `_job_batch("evening", 2, "livelihood")` | 18:35 | 民生类 2 篇。 |
| `sync_published_articles` | `_job_sync_published()` | 03:17 | 同步公众号后台已发布文章。 |

## 高副作用 API

这些 API 可能调用 LLM、微信、图片生成、数据库写入或真实发布。除非用户明确要求，不要自动调用：

```text
POST /api/v1/articles/publish
POST /api/v1/articles/batch/{batch_type}
POST /api/v1/scheduler/trigger/{job_id}
```

`POST /api/v1/articles/preview` 也会调用 LLM 和搜索接口，成本较高。
