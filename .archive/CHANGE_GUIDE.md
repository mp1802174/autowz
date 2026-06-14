# 修改指南：需求到代码位置

本文件用于把常见维护需求快速映射到应阅读/修改的文件。新 AI 接手时，先根据用户需求在这里定位，再打开具体文件。

## 1. 修改 API 路由、请求参数、响应字段

优先看：

1. `app/api/routes/articles.py`
2. `app/api/routes/scheduler.py`
3. `app/api/routes/health.py`
4. `app/models/schemas.py`
5. `docs/API_MAP.md`

注意：

- 新增 API 时要在对应 route 文件添加函数和 Pydantic schema。
- 如果新增一个路由模块，要在 `app/api/router.py` 挂载。
- 修改 `API_PREFIX` 相关逻辑看 `app/core/config.py` 和 `app/api/router.py`。
- API 可能触发真实 LLM/微信发布，测试时优先 mock。

## 2. 修改完整发文流水线

优先看：

1. `app/services/pipeline.py`
2. `app/services/writer/service.py`
3. `app/services/humanizer/service.py`
4. `app/services/guard/service.py`
5. `app/services/wechat/service.py`
6. `app/db/crud.py`

关键方法：

- `ArticlePipeline.generate_preview()`：预览链路。
- `ArticlePipeline.publish()`：手动指定话题发布。
- `ArticlePipeline.collect_topics()`：采集新闻池并入库。
- `ArticlePipeline.run_batch()`：自动批次。
- `ArticlePipeline._process_single_article()`：单篇自动发文完整流程。

注意：

- 自动批次会写 `topics/articles/wechat_publish_records`。
- 手动 publish 当前不保存 Article/PublishRecord，只返回结果。
- `style_score < 80` 不发布，自动批次最多重试 humanizer 3 次。
- 风险 high 直接失败；不要绕过风控。

## 3. 修改新闻/热点采集来源

优先看：

1. `app/services/collector/search.py`
2. `app/services/collector/weibo.py`
3. `app/services/collector/baidu.py`
4. `app/services/collector/manager.py`
5. `app/services/pipeline.py`

当前主流程用：

- `NewsCollector.fetch_news_pool()`：天行 API + RSS。
- `NewsCollector.fetch_topic_detail()`：搜狗新闻搜索。

旧热点模块：

- `WeiboCollector.collect()`
- `BaiduCollector.collect()`
- `CollectorManager.collect_all()`

注意：

- 如果新增新闻源，优先返回 `NewsItem` 或 `CollectedTopic`，并做好标题去重。
- 外部抓取失败应返回空列表并记录 warning/error，不要让整个批次崩溃。
- `TIANAPI_KEY` 为空时要能降级到 RSS。

## 4. 修改选题逻辑、分类优先级、fallback 排序

优先看：

1. `app/services/selector/service.py`
2. `app/services/guard/blocklist.py`
3. `tests/test_selector.py`

关键位置：

- `SYSTEM_PROMPT`：默认选题提示词。
- `CATEGORY_PROMPTS`：finance/entertainment/livelihood 分类选题提示词。
- `PRIORITY_KEYWORDS`：财经、民生、领导人等优先关键词。
- `TopicSelectorService.select()`：LLM 选题。
- `_fallback_select()` / `_priority_score()`：LLM 失败时的兜底排序。

注意：

- 自动批次传入 category：早 finance，中 entertainment，晚 livelihood。
- medium/high 风险选题应被自动管线过滤或降权。
- 修改关键词后同步测试。

## 5. 修改文章生成提示词、标题/摘要解析、fallback 文稿

优先看：

1. `app/services/writer/service.py`
2. `app/services/content_length.py`
3. `tests/test_content_length.py`

关键位置：

- `SYSTEM_PROMPT`：作者人设和写作总要求。
- `WriterService.generate()`：调用 LLM 生成文章。
- `_parse_response()`：从 LLM 输出提取标题、摘要、正文。
- `_fallback()`：LLM 调用或解析失败时兜底。
- `finalize_article()`：字数截断与字数后缀。

注意：

- 当前文章目标约 200-300 字，事实约 3/4、观点约 1/4。
- LLM 输出解析要兼容模型输出额外说明/思维过程。
- 不要在提示词中加入会触发平台风险的表达。

## 6. 修改人味化改写、扩写、段落和字数控制

优先看：

1. `app/services/humanizer/service.py`
2. `app/services/content_length.py`
3. `tests/test_content_length.py`

关键位置：

- `SYSTEM_PROMPT`：改写准则。
- `HumanizerService.rewrite()`：改写主入口。
- `_expand_short_article()`：短文补足。
- `_fallback_expand_short_article()`：兜底扩写。
- `_split_long_paragraphs()` / `_trim_to_limit()`：排版和截断。

注意：

- 改写结果过短时会扩写或回退原文。
- `style_score` 会影响是否发布。
- 保持事实优先，禁止新增无依据事实。

## 7. 修改风控词库或审核策略

优先看：

1. `app/services/guard/blocklist.py`
2. `app/services/guard/service.py`
3. `tests/test_guard.py`
4. `app/services/pipeline.py` 中 publish/run_batch 风控调用

关键函数：

- `match_high_risk()`
- `match_medium_risk()`
- `is_topic_blocked()`
- `is_topic_risky()`
- `GuardService.review()`

注意：

- `HIGH_RISK_TERMS` 命中即 high。
- `MEDIUM_RISK_TERMS` 命中 medium。
- 自动管线应尽量避开 high/medium。
- 降低风控强度前必须有明确用户要求和风险认知。

## 8. 修改 LLM 客户端、模型、重试、JSON 解析

优先看：

1. `app/services/llm/client.py`
2. `app/core/config.py`
3. `.env.example`

关键位置：

- `LLMClient.__init__()`：读取 `OPENAI_API_KEY/BASE_URL/MODEL`。
- `chat_completion()`：流式调用，3 次重试。
- `json_completion()`：要求 JSON 输出。
- `_extract_json()`：从模型输出中提取 JSON。

注意：

- 兼容 OpenAI 风格 API 和自定义 base_url。
- 不要记录 API key。
- 修改 JSON 解析要保留对 markdown code block 和额外文本的容错。

## 9. 修改微信草稿/发布/API 调用

优先看：

1. `app/services/wechat/service.py`
2. `app/services/wechat/client.py`
3. `app/services/wechat/token_service.py`
4. `app/services/wechat/material_service.py`
5. `app/services/wechat/draft_service.py`
6. `app/services/wechat/publish_service.py`
7. `app/models/schemas.py`

关键流程：

```text
WechatPublishOrchestrator.publish_article()
  → upload_image()
  → upload_temp_image()
  → create_draft()
  → submit_publish() 可选
  → poll_until_complete() 可选
```

注意：

- `WECHAT_ENABLE_AUTO_PUBLISH=false` 时只创建草稿。
- `WECHAT_FALLBACK_TO_DRAFT=true` 时发布失败尽量保留草稿。
- token 过期错误码在 `client.py` 的 `TOKEN_EXPIRED_CODES`。
- 微信 API 返回 `errcode != 0` 会抛 `WechatAPIError`。

## 10. 修改封面图生成和图片 provider

优先看：

1. `app/services/wechat/cover_generator.py`
2. `image_providers.example.json`
3. `image_providers.json`（敏感，默认不要展示）
4. `scripts/test_image_providers.py`

关键位置：

- `generate_cover_async()` / `generate_cover()`：对外入口。
- `_build_image_providers()`：读取 provider JSON。
- `_generate_with_provider()` / `_do_call_provider()`：调用 provider。
- `_image_bytes_from_*()`：解析 URL/base64/data URI/JSON。
- `_crop_to_cover_ratio()`：裁剪为公众号封面比例。
- `_generate_text_cover()`：Pillow 文字封面兜底。

注意：

- provider 配置可能含 API key，不要泄漏。
- 图片测试会真实调用 provider，需用户确认。
- 失败时应保留文字封面兜底。

## 11. 修改底部“精彩文章导读”或已发布文章同步

优先看：

1. `app/services/wechat/reading_guide.py`
2. `app/services/wechat/publish_sync.py`
3. `app/services/wechat/mp_backend.py`
4. `app/db/crud.py` 的 `get_random_published_articles()`
5. `app/tasks/scheduler.py` 的 `_job_sync_published()`

注意：

- `mp_backend.py` 使用微信公众平台后台内部接口，依赖 `/root/cc/newwz/data/id_info.json`。
- 频繁调用可能触发微信风控。
- 同步逻辑按标题精确匹配 `articles` 表。
- 导读区块要求文章有成功发布 URL 和正文中可提取 `<img>`。

## 12. 修改定时任务时间、数量、分类

优先看：

1. `app/tasks/scheduler.py`
2. `app/api/routes/scheduler.py`
3. `README.md`
4. `docs/API_MAP.md`

关键位置：

- `init_scheduler()` 中 `scheduler.add_job(...)`。
- `_job_collect()`。
- `_job_batch(batch_type, count, category)`。
- `_job_sync_published()`。

注意：

- 修改 job id 会影响 `/api/v1/scheduler/trigger/{job_id}`。
- 修改文章数量可能增加 LLM/图片/微信调用成本。
- 分类参数会影响 selector prompt。

## 13. 修改数据库结构或查询

优先看：

1. `app/db/models.py`
2. `app/db/crud.py`
3. `app/db/engine.py`
4. `scripts/init_db.py`
5. `docs/DATABASE.md`

注意：

- 当前没有 Alembic 迁移；`init_db()` 只 `create_all`，不会自动修改已有表结构。
- 生产库改字段需要手写迁移 SQL 或引入 Alembic。
- 新增字段要同步 Pydantic schema、CRUD、API 返回和文档。

## 14. 修改配置

优先看：

1. `app/core/config.py`
2. `.env.example`
3. `docs/CONFIGURATION.md`
4. `docker-compose.yml`

注意：

- `Settings` 使用 alias 映射环境变量。
- 新增配置必须给默认值或更新 `.env.example`。
- 不要把 `.env` 里的真实密钥写入文档。

## 15. 修改测试

优先看：

1. `tests/*.py`
2. `pyproject.toml` pytest 配置
3. 被测模块

建议：

- 对 LLM、微信、图片 provider、外部新闻源使用 mock。
- 不要让单元测试真实发布或真实调用高成本 API。
- 修改风控/选题/字数控制后补充对应测试。
