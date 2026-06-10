# 架构说明

## 总体分层

```text
HTTP/API 层          app/main.py, app/api/routes/*
  ↓
业务编排层           app/services/pipeline.py ArticlePipeline
  ↓
领域服务层           collector / selector / writer / humanizer / guard / wechat
  ↓
基础设施层           LLMClient / SQLAlchemy / httpx / WeChat API / image providers
  ↓
数据层               MySQL tables: topics, articles, wechat_publish_records
```

## FastAPI 启动流程

```text
uvicorn app.main:app
  ↓
app/main.py 创建 FastAPI app
  ↓
lifespan 启动
  ├─ setup_logging()
  ├─ init_db()                # Base.metadata.create_all
  ├─ init_scheduler()         # 注册并启动 APScheduler jobs
  └─ 服务启动完成
```

关闭时：

```text
lifespan shutdown → shutdown_scheduler()
```

## 完整发文流程

`ArticlePipeline._process_single_article()` 是自动批次单篇文章主链路。

```text
NewsItem
  ↓
保存 Topic(status=selected)
  ↓
NewsCollector.fetch_topic_detail() 搜索详细报道
  ↓
WriterService.generate() 生成 draft
  ↓
保存 Article(status=drafted)
  ↓
HumanizerService.rewrite() 人味化改写
  ↓
更新 Article(status=humanized)
  ↓
GuardService.review() 风控审核
  ↓
更新 Article(status=reviewed, risk_level=...)
  ↓
如果 high → Article(status=failed)，停止
  ↓
如果 style_score < 80 → 最多重试 humanizer 3 次
  ↓
如果仍低分 → 返回 low_quality，不发布
  ↓
追加底部精彩文章导读
  ↓
generate_cover_async() 生成封面
  ↓
Article(status=publishing)
  ↓
WechatPublishOrchestrator.publish_article()
  ├─ upload_image() 上传封面永久素材
  ├─ upload_temp_image() 上传正文图
  ├─ create_draft() 创建草稿
  ├─ 如果 WECHAT_ENABLE_AUTO_PUBLISH=false → 返回 draft_created
  ├─ submit_publish() 提交发布
  └─ poll_until_complete() 轮询结果
  ↓
保存 WechatPublishRecord
  ↓
Article(status=published/success/failed/...)
```

## 预览流程

`ArticlePipeline.generate_preview()`：

```text
ArticlePreviewRequest(topic, stance)
  ↓
NewsCollector.fetch_topic_detail()
  ↓
WriterService.generate()
  ↓
HumanizerService.rewrite()
  ↓
GuardService.review()
  ↓
ArticlePreviewResponse
```

预览不写 `articles` 表，也不调用微信发布。

## 手动发布流程

`ArticlePipeline.publish()`：

```text
PublishArticleRequest
  ↓
is_topic_risky() 早期风险拦截
  ↓
generate_preview()
  ↓
风险 high 或 style_score < 80 → ValueError
  ↓
追加导读区块
  ↓
生成/使用封面
  ↓
WechatPublishOrchestrator.publish_article()
  ↓
PublishArticleResponse
```

注意：当前手动 publish 路径不保存 Article/PublishRecord 到数据库，主要返回发布结果。自动批次路径会落库。

## 采集和选题

自动批次 `run_batch()`：

```text
NewsCollector.fetch_news_pool()
  ├─ 天行 API 国内/财经/社会新闻（如果 TIANAPI_KEY 存在）
  └─ RSS 新华社/人民网
  ↓
按规范化标题去重
  ↓
查询近 3 天 selected topics
  ↓
相似标题过滤，避免重复选题
  ↓
TopicSelectorService.select()
  ├─ LLM JSON 选题
  └─ fallback 选题：财经/国际/领导人等优先，娱乐八卦降权
```

另有旧热点采集模块：`collector/weibo.py`, `collector/baidu.py`, `collector/manager.py`，主要用于微博/百度热搜采集与测试，目前主流水线 `ArticlePipeline.collect_topics()` 使用的是 `NewsCollector.fetch_news_pool()`。

## 风控架构

```text
选题/手动发布早期：guard/blocklist.py
  ├─ HIGH_RISK_TERMS：高风险
  ├─ MEDIUM_RISK_TERMS：中风险
  └─ DOWNRANK_TERMS：选题降权

文章审核：GuardService.review()
  ├─ match_high_risk(text) → high，直接拦截
  ├─ match_medium_risk(text) → medium，建议审查
  └─ LLM json_completion 深度审核
```

注意：`is_topic_risky()` 对 high/medium 都返回 risky，自动批次应避开。不要随意降低风控强度。

## 数据库状态

### topics.status

```text
collected → selected → used（预留/可能未完全使用）
```

当前自动批次保存 selected，采集保存 collected。

### articles.status

```text
drafted → humanized → reviewed → publishing → published/success/draft_created/failed/low_quality(返回状态)
```

模型注释中列出：`drafted/humanized/reviewed/publishing/published/failed`。实际代码可能把微信返回状态写入 `Article.status`，维护时要注意兼容。

### wechat_publish_records.publish_status

常见值：

- `pending`
- `submitted`
- `success`
- `draft_created`
- `fallback_error`
- `submit_failed_draft_kept`
- `publish_failed_draft_kept`

## 微信发布降级策略

`WECHAT_ENABLE_AUTO_PUBLISH=false`：只创建草稿，不提交发布。  
`WECHAT_FALLBACK_TO_DRAFT=true`：提交或发布失败时尽量保留草稿并返回 draft_only/fallback 状态。

Token 过期错误码在 `app/services/wechat/client.py`：

```text
40001, 40014, 42001
```

遇到这些错误时 `WechatPublishOrchestrator` 会 invalidate token 并重试。

## 封面图生成架构

```text
generate_cover_async(title, content)
  ↓
_generate_ai_cover()
  ├─ 读取 image_providers.json
  ├─ 依次尝试 provider/model
  ├─ 兼容 /images/generations 和 /chat/completions
  └─ 下载/解码图片 bytes
  ↓
_crop_to_cover_ratio()
  ↓
保存到 drafts/

失败时：_generate_text_cover() 使用 Pillow 生成文字封面
```

`image_providers.json` 可能含 API key，默认不要读取/展示。

## 已发布文章同步

```text
_job_sync_published()
  ↓
publish_sync.sync_published_articles()
  ↓
WechatMpBackend.list_published_articles()
  ├─ 读取 /root/cc/newwz/data/id_info.json 的 token/cookie
  └─ 调用 mp.weixin.qq.com 后台内部接口
  ↓
按 title 精确匹配 articles 表
  ↓
回填 WechatPublishRecord.article_url，状态置 success
```

注意：这是微信公众平台后台内部接口，依赖另一个项目 `newwz` 的扫码登录态。调用频率应低，避免风控。
