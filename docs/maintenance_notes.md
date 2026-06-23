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

## 2026-06-23：质量防线重构 + 项目级prompt架构 + gpt-5.5首选

### Git 提交

- `a95dbfe`：内容质量防线 + gpt-5.5 首选模型 + 三时段定时
- `10f4056`：项目级prompt架构 + 质量闸柔性字数 + 头条重试 + 第一人称/媒体名禁令

当前分支：`feat/quality-gate-and-gpt55`(从 main 开出,未合回)

### 触发背景

6-22 文章《别了老将！中超保级队的阵容大清洗从来不讲体面》(id=337)出现严重退化:正文末段 490 字一句到底、结尾"消失在。"被硬截断,却以 style_score=85/risk=low 通过审核并存入三渠道草稿。排查发现四层防线同时失守:LLM 退化、截断补句号美容废稿、风控无质量维度、style_score 硬编码 85。

### 新增文件

| 文件 | 用途 |
|------|------|
| `app/services/quality/` | 规则版质量闸(check_quality),拦截退化长句/断头结尾/畸形段落/片段重复/字数不足 |
| `app/services/prompts/base.py` | 项目级 BASE_SYSTEM_PROMPT,所有模块共享的基础约束 |
| `tests/test_quality_checker.py` | 质量闸单测(含退化文本拦截用例) |

### 架构变更

1. **质量闸接入生产链路**:`finance/module.py` 的 `_process_single_article` 先过质量闸,不合格重生成 1 次仍不合格→弃稿。style_score 从硬编码 85 改为 check_quality 真实分。

2. **截断逻辑修复**:`content_length.py` 的 `trim_markdown_to_max_chars` 不再字符级硬切+补句号伪装完整,改为只裁到原文已有句末标点。

3. **风控增强**:`guard/service.py` 新增"语义质量"维度,LLM 失败不再默认放行(规则质量分兜底)。

4. **字数策略**:差<10%只扣分不否决(差几个字≠低质),差>10%才硬否决。

5. **头条发布重试**:`toutiao.py` 发布 API 调用失败自动重试 1 次。

### 定时配置变更

`entertainment/config.py`:
```python
SCHEDULE_SLOTS = [
    ScheduleSlot(hour=12, minute=5, batch_type="noon", count=1),
    ScheduleSlot(hour=15, minute=5, batch_type="afternoon", count=1),
    ScheduleSlot(hour=18, minute=5, batch_type="evening", count=1),
]
```
时间为北京时间(scheduler.py 已显式锁 `timezone="Asia/Shanghai"`,机器本地 JST)。

### 模型配置

`.env`(不入 git):
```
OPENAI_MODEL=sharedchat/gpt-5.5
LLM_FALLBACK_MODELS=gpt-5.5,claude-opus-4-6,kimi-k2.6,deepseek-v4-pro,kimi-k2p5,gpt-oss-120b,google/gemma-4-31b-it
```

8317(本机 CLIProxyAPI,`/root/cc/CLIProxyAPI`,另一 git 仓库):
- `config.yaml`:sharedchat 配为 `codex-api-key` 上游(prefix=sharedchat),非 openai-compat。`disable-cooling: false`(429 指数退避,503 固定 1min)。
- auth-dir:`/root/.cli-proxy-api`(OAuth token 文件存放,目前有 29 个 codex token)。
- systemd:`cliproxyapi.service`

### 已知问题

- **头条号偶发超时**:15:05 批次头条超时,后续冒烟测试通过。大概率偶发网络波动。cookie(sid_guard/passport_auth_status 等)均未过期(最近 26 天后)。
- **gpt-5.5 OAuth 已可用但 sharedchat 公益站不稳定**:经 8317 OAuth 29 token 的 `gpt-5.5` 稳定可用;`sharedchat/gpt-5.5` 静态 key 走 sharedchat 公益站,额度限流频繁。fallback 链设计为 sharedchat→OAuth→claude→... 自动切换。
- **生图 fallback 未完成**:sharedchat 的 gpt-image-2 接口协议不兼容(需适配 Codex Responses API),暂搁置。

### 验证命令

```bash
# 查看服务
systemctl status autowz cliproxyapi --no-pager

# 查看模型可用性
.venv/bin/python -c "
import asyncio
from openai import AsyncOpenAI
async def t(m):
    c=AsyncOpenAI(api_key='sk-760516666',base_url='http://140.238.201.162:8317/v1')
    s=await c.chat.completions.create(model=m,messages=[{'role':'user','content':'hi'}],max_tokens=5)
    print(f'{m}: {s.choices[0].message.content}')
asyncio.run(t('gpt-5.5'))
"

# 跑测试
.venv/bin/python -m pytest -q
```

