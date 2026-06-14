# 数据库说明

数据库层基于 SQLAlchemy，配置在 `app/db/engine.py`，模型在 `app/db/models.py`，常用查询在 `app/db/crud.py`。

## 初始化

```bash
python scripts/init_db.py
```

内部调用：

```text
scripts/init_db.py → app.db.engine.init_db() → Base.metadata.create_all(get_engine())
```

注意：当前没有 Alembic。`create_all` 不会自动变更已存在表结构。

## 表：topics

模型：`app.db.models.Topic`

| 字段 | 说明 |
|---|---|
| `id` | 主键。 |
| `title` | 话题标题。 |
| `source` | 来源，例如 RSS、天行 API、weibo、baidu。 |
| `hot_score` | 热度分。 |
| `conflict_score` | 冲突/争议分，当前使用有限。 |
| `summary` | 摘要。 |
| `source_url` | 原始链接。 |
| `collected_at` | 采集时间。 |
| `batch_date` | 批次日期。 |
| `status` | `collected/selected/used`。 |

索引：

- `batch_date`
- `ix_topics_batch_status(batch_date, status)`

相关 CRUD：

- `save_topic()`
- `save_topic_upsert()`：按 `title + batch_date` 去重。
- `get_topics_by_date()`
- `get_selected_topics()`
- `get_recent_selected_topics()`
- `update_topic_status()`

## 表：articles

模型：`app.db.models.Article`

| 字段 | 说明 |
|---|---|
| `id` | 主键。 |
| `topic_id` | 关联 `topics.id`，可空。 |
| `article_type` | 文章类型，目前多为 `comment`。 |
| `title` | 标题。 |
| `digest` | 摘要。 |
| `content_md` | Markdown 正文。 |
| `content_html` | HTML 正文。 |
| `style_score` | 风格/质量评分。 |
| `risk_level` | `low/medium/high`。 |
| `status` | 文章状态。 |
| `scheduled_at` | 预定时间，可空。 |
| `published_at` | 发布时间，可空。 |
| `created_at` | 创建时间。 |
| `updated_at` | 更新时间。 |

模型注释状态：

```text
drafted/humanized/reviewed/publishing/published/failed
```

实际运行还可能写入微信返回状态，例如 `success`, `draft_created` 等。维护时要兼容历史数据。

相关 CRUD：

- `save_article()`
- `get_article_by_id()`
- `update_article_status()`
- `get_articles_by_status()`

## 表：wechat_publish_records

模型：`app.db.models.WechatPublishRecord`

| 字段 | 说明 |
|---|---|
| `id` | 主键。 |
| `article_id` | 关联 `articles.id`。 |
| `draft_media_id` | 微信草稿 media_id。 |
| `publish_id` | 微信发布任务 ID。 |
| `article_url` | 文章 URL。 |
| `publish_status` | 发布状态。 |
| `raw_response` | 原始响应 JSON。 |
| `cover_media_id` | 封面素材 media_id。 |
| `created_at` / `updated_at` | 时间。 |

相关 CRUD：

- `save_publish_record()`
- `update_publish_record()`
- `get_pending_publish_records()`
- `get_random_published_articles()`：底部导读区块使用。

## Schema 变更建议

如果要新增字段：

1. 修改 `app/db/models.py`。
2. 修改相关 CRUD。
3. 修改 API response/Pydantic schema（如需要）。
4. 编写手动 SQL 迁移，或引入 Alembic。
5. 不要依赖 `create_all()` 修改已有表。
6. 更新本文档和测试。
