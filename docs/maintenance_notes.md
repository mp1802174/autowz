# autowz 维护记录与关键坑位

> 给后续 AI / 人类维护者快速接手用。每次改生产链路、渠道接口、定时配置后，请在本文件追加记录。

## 2026-06-21：LLM 生成文章并保存三渠道草稿

### 当前生产目标

- 生产链路：采集真实新闻池 → 自动选题 → LLM 生成正式文章 → 风控审核 → AI 封面 → 保存各渠道草稿。
- 当前定时模块：`ACTIVE_MODULE=entertainment`
- 当前定时任务：
  - `collect_hot_topics`：每 30 分钟采集热点。
  - `batch_entertainment_daily`：每天 `16:20` 生成 1 篇文章。
  - `sync_published_articles`：每天 `03:17` 同步公众号已发布文章。
- 当前发布目标已改为三渠道：
  ```env
  PUBLISH_TARGETS=wechat,toutiao,baijiahao
  WECHAT_ENABLE_AUTO_PUBLISH=false
  ```
- systemd 服务：`autowz.service`，重启命令：
  ```bash
  systemctl restart autowz
  ```

### 已验证的生产结果

- 生产链路实测已完成：真实新闻池、自动选题、LLM 生成、审核、封面、微信/头条/百家号保存草稿。
- 实测文章：`年轻人开始流行“没苦硬吃”了`
- 本地 `article_id=336`
- 结果：
  - 微信：`draft_created`
  - 头条：`draft_saved`
  - 百家号：`draft_saved`
- 相关日志：
  - `production_all_channels_current_20260621_211919.log`
  - `channel_fix_verify_20260621_211701.log`
- 单测：`18 passed`
- Git 提交：`a1c83b5 LLM生成文章并发布三渠道草稿成功`

### 核心代码改动

#### 1. 导读区块只允许微信公众号使用

问题：`精彩文章导读` 原先在主链路统一拼接，导致头条/百家号也出现。

修复：
- 删除主链路统一拼接导读：
  - `app/modules/finance/module.py`
  - `app/services/pipeline.py`
- 只在微信渠道内部追加导读：
  - `app/services/publish/channels/wechat.py`
- 头条/百家号发布前会主动剥离导读：
  - `ToutiaoChannel._strip_wechat_guide()`
  - `BaijiahaoChannel._strip_wechat_guide()`

#### 2. 所有渠道只保存草稿，不自动正式发布

修复：
- 微信：`WechatPublishOrchestrator.publish_article(..., force_draft=True)`，不走自动发布。
- 头条：固定草稿参数，见下面“头条重要坑位”。
- 百家号：固定 `is_draft=1`。
- 文章本地状态：渠道成功后写 `draft_saved`，不再写 `published`。

#### 3. 头条号重要坑位：`save=0` 才是草稿

⚠️ 不要改回 `save=1`。

头条前端枚举是：

```js
PUBLISH = 0
DRAFT = 1
```

但提交接口字段 `save` 的语义相反：

```text
save=1 => 发表 / 直接发布
save=0 => 保存草稿
```

当前代码：

```python
ToutiaoChannel.DRAFT_SAVE_MODE = "0"
```

接口：

```text
POST /mp/agw/article/publish?source=mp&type=article&aid=1231&mp_publish_ab_val=0
```

如果用户反馈“头条直接发布”，第一时间检查：

```bash
grep -n "DRAFT_SAVE_MODE\\|fd.append('save'" app/services/publish/channels/toutiao.py
```

必须保持 `DRAFT_SAVE_MODE = "0"`。

#### 4. 头条/百家号配图修复

头条：
- 图片上传接口：
  ```text
  /spice/image?upload_source=20020003&aid=1231&device_platform=web&need_cover_url=1
  ```
- FormData 字段必须是：`image`
- 上传后：
  - 正文顶部插入 `<img>`
  - `pgc_feed_covers` 设置封面

百家号：
- 图片上传接口：
  ```text
  /materialui/picture/uploadProxy
  ```
- FormData 字段必须是：`media`
- 上传后：
  - 正文顶部插入 `<img>`
  - `cover_images` 设置封面

### 维护验证命令

查看定时器：

```bash
curl -sS http://127.0.0.1:8000/api/v1/scheduler/status
```

查看服务：

```bash
systemctl status autowz --no-pager
```

查看当前发布目标：

```bash
.venv/bin/python - <<'PY'
from app.core.config import get_settings
s=get_settings()
print(s.active_module, s.publish_targets, s.wechat_enable_auto_publish)
PY
```

跑单测：

```bash
.venv/bin/python -m pytest -q
```

### 注意事项

- 不要随意跑全生产链路测试；会真实在平台创建草稿，头条参数错误时还可能误发。
- 如需验证头条草稿参数，优先读官方前端 JS 或做无提交检查，不要反复提交文章。
- `.env` 已设置三渠道发布，但 `.env` 通常不入 Git；迁移机器时要手动确认 `PUBLISH_TARGETS`。

