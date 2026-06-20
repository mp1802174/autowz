# GUIDE - autowz 完整使用指南

**版本**: v2.0  
**更新时间**: 2026-06-19

> 本文档包含模块化设计、配置详解、扩展开发等进阶内容

---

## 📑 目录

1. [模块化架构](#1-模块化架构)
2. [配置详解](#2-配置详解)
3. [如何新增模块](#3-如何新增模块)
4. [Writer 开发指南](#4-writer-开发指南)
5. [API 参考](#5-api-参考)
6. [故障排查](#6-故障排查)
7. [最佳实践](#7-最佳实践)
8. [运营战略方案与可行性裁决](#8-运营战略方案与可行性裁决2026-06-18)

---

## 1. 模块化架构

### 1.1 设计理念

系统支持**多套完全独立的内容配方**,每个模块有自己的:
- **选题策略**: 不同关键词、数据源、优先级
- **作者人设**: 不同署名和风格定位  
- **内容结构**: 数据解读 vs 情绪共鸣 vs 视频精华
- **新闻来源**: AKShare+搜狗 vs 微博热搜 vs YouTube
- **发布频率**: 每天1篇 vs 3篇 vs 实时追热点
- **字数风格**: 650-750字理性 vs 800-1000字情绪化

**公共能力复用**: 所有模块共享 LLM/发布/审核/数据库/封面/导读。

### 1.2 架构图

```
app/modules/
  ├── base.py              # BaseContentModule 抽象基类
  ├── registry.py          # 模块注册表
  │
  ├── finance/             # 财经模块(已实现)
  │   ├── config.py        # 配置参数
  │   ├── writer.py        # DataDrivenWriter
  │   └── module.py        # FinanceModule
  │
  └── (待扩展)
      ├── entertainment/   # 娱乐模块
      ├── video/           # 视频模块
      └── policy/          # 政策解读模块
```

### 1.3 抽象基类

所有模块必须实现以下接口:

```python
class BaseContentModule(ABC):
    @property
    def module_name(self) -> str:
        """模块唯一标识"""
    
    @property
    def display_name(self) -> str:
        """显示名称"""
    
    @property
    def author(self) -> str:
        """作者署名"""
    
    async def collect_topics(self) -> List[NewsItem]:
        """采集选题池"""
    
    async def select_topics(self, pool, count) -> List[NewsItem]:
        """从池中选题"""
    
    async def generate_article(self, topic) -> dict:
        """生成文章"""
    
    async def run_batch(self, count) -> List[dict]:
        """执行完整批次"""
```

### 1.4 切换模块

```python
from app.services.pipeline import ArticlePipeline

# 财经模块
pipeline = ArticlePipeline("finance")
await pipeline.run_batch("morning", 1)

# 娱乐模块
pipeline = ArticlePipeline("entertainment")
await pipeline.run_batch("afternoon", 1)

# 不传参数时读取 ACTIVE_MODULE；默认 finance
pipeline = ArticlePipeline()
```

---

## 2. 配置详解

### 2.1 环境变量(.env)

```bash
# 微信公众号(必填)
WECHAT_APP_ID=wx43bfc1d5636565cb
WECHAT_APP_SECRET=ae88882163c9033016c9f6e0e0b97cab
WECHAT_ENABLE_AUTO_PUBLISH=false  # 是否自动发布(false=仅草稿)
WECHAT_FALLBACK_TO_DRAFT=true     # 失败时是否降级为草稿模式

# LLM(OpenAI兼容接口,必填)
OPENAI_API_KEY=sk-760516666
OPENAI_BASE_URL=http://140.238.201.162:8317/v1
OPENAI_MODEL=gpt-5.5

# 新闻API(必填)
TIANAPI_KEY=7278ed57991da4a55e4df2ded77ca580

# 数据库(必填)
MYSQL_DSN=mysql+pymysql://root:1c8034bf4061cbd6@localhost:3306/autowz?charset=utf8mb4

# 作者署名(可选)
CONTENT_AUTHOR=现象观察

# 当前启用模块；默认 finance。可选 finance / entertainment
ACTIVE_MODULE=finance

# 评论设置(可选)
DEFAULT_COMMENT_OPEN=1          # 默认开启评论
DEFAULT_FANS_COMMENT_ONLY=0     # 所有人可评论
```

### 2.2 模块配置

每个模块在 `app/modules/<模块名>/config.py` 中独立配置:

```python
# app/modules/finance/config.py

MODULE_NAME = "finance"
DISPLAY_NAME = "财经观察"
AUTHOR = "现象观察"

# 选题策略
SELECTOR_CONFIG = {
    "priority_keywords": {
        "finance": ["财经", "经济", "gdp", "cpi", "股市", ...],
        "leaders": ["总统", "总理", "主席", ...],
    },
    "downrank_keywords": ["明星", "恋情", "八卦", ...],
    "blacklist_keywords": ["娱乐", "体育", "游戏", ...],
}

# 写作配置
WRITER_CONFIG = {
    "min_chars": 650,
    "max_chars": 750,
    "temperature": 0.7,
    "style": "data_driven_analysis",
    "structure": "hook-data-analysis-impact-conclusion",
}

# 调度配置
SCHEDULE_SLOTS = [
    ScheduleSlot(hour=7, minute=30, batch_type="daily", count=1),
]
```

### 2.3 定时任务配置

在各模块 `config.py` 的 `SCHEDULE_SLOTS` 中配置。调度器只注册 `ACTIVE_MODULE` 对应模块的任务:

```python
# 财经模块: 每天早上 7:30
SCHEDULE_SLOTS = [
    ScheduleSlot(hour=7, minute=30, batch_type="daily", count=1),
]

# 娱乐模块: 每天下午 16:20
SCHEDULE_SLOTS = [
    ScheduleSlot(hour=16, minute=20, batch_type="daily", count=1),
]
```

---

## 3. 如何新增模块

### 3.1 新增娱乐模块示例

#### 步骤1: 创建目录
```bash
mkdir -p app/modules/entertainment
```

#### 步骤2: 创建配置 (config.py)
```python
MODULE_NAME = "entertainment"
DISPLAY_NAME = "娱乐吃瓜"
AUTHOR = "吃瓜群众"

SELECTOR_CONFIG = {
    "priority_keywords": {
        "entertainment": ["明星", "恋情", "爆料", "热搜", "八卦"],
    },
}

WRITER_CONFIG = {
    "min_chars": 800,
    "max_chars": 1000,
    "style": "emotional_resonance",
}

SCHEDULE_SLOTS = [
    ScheduleSlot(hour=13, minute=0, batch_type="daily", count=1),
]
```

#### 步骤3: 创建 Writer (writer.py)
```python
class EmotionalWriter:
    """情绪共鸣型写作器"""
    
    async def generate(self, topic, context_text):
        system_prompt = """
你是娱乐号作者,写爆料/反转/情绪共鸣型文章。

结构:
1. 反转开头(50-80字)
2. 爆料细节(300-400字)
3. 网友反应(200-300字)
4. 观点(200-300字)

禁止: 理性分析、数据堆砌、官腔
风格: 口语化、情绪化、有态度
"""
        # ... 调用 LLM
```

#### 步骤4: 创建模块 (module.py)
```python
from app.modules.base import BaseContentModule

class EntertainmentModule(BaseContentModule):
    @property
    def module_name(self): return "entertainment"
    
    async def collect_topics(self):
        # 从微博热搜采集
        return await self.weibo_collector.fetch_hot()
    
    async def generate_article(self, topic):
        # 用 EmotionalWriter 生成
        return await self.writer.generate(topic.title, ...)
```

#### 步骤5: 注册模块
```python
# app/modules/registry.py
MODULE_REGISTRY = {
    "finance": _get_finance_module,
    "entertainment": _get_entertainment_module,  # 新增
}
```

#### 步骤6: 配置定时任务
```python
# app/tasks/scheduler.py
scheduler.add_job(
    _job_batch,
    CronTrigger(hour=13, minute=0),
    args=["entertainment", 1],
    id="entertainment_daily",
)
```

---

## 4. Writer 开发指南

### 4.1 财经模块 Writer(已实现)

**文件**: `app/modules/finance/writer.py`

**Prompt 核心要求**:
```
1. 钩子开头(50-80字): 反常识数字/反差,禁止"据X报道"
2. 数据呈现(200-250字): 核心数字+对比+来源,用 Markdown 表格
3. 解读分析(200-250字): 驱动因素+横向对比
4. 影响推演(100-150字): 产业链/消费者/投资影响
5. 明确判断(50-80字): 清晰结论

严禁:
- AI套话("在这个时代""不得不说""众所周知")
- 机械序列词("首先/其次/最后""综上所述")
- 整齐排比和工整对仗
- "据X报道"开头和"从市场逻辑看"套话
```

**关键代码**:
```python
content_html = md_lib.markdown(
    content_md,
    extensions=['tables']  # 启用表格支持
)
```

### 4.2 娱乐模块 Writer(示例)

**Prompt 核心要求**:
```
1. 反转开头(50-80字): 爆料/反常识/反转
2. 爆料细节(300-400字): 时间线/当事人反应
3. 网友反应(200-300字): 热评/争议点
4. 观点(200-300字): 你的态度,不骑墙

风格:
- 口语化、情绪化、有态度
- 多用"说句不中听的""实际上""问题是"
- 禁止理性分析、数据堆砌
```

### 4.3 开发规范

1. **类型提示**: 所有函数必须有完整类型提示
2. **文档字符串**: 公开方法必须有 docstring
3. **错误处理**: 必须有 LLM 调用失败的兜底逻辑
4. **日志记录**: 关键步骤必须记录 log
5. **字数控制**: 使用 `finalize_article` 裁剪到上限

---

## 5. API 参考

### 5.1 预览文章

```bash
POST /api/v1/articles/preview
Content-Type: application/json

{
  "topic": "美联储降息预期",
  "stance": "谨慎观望"
}
```

**响应**:
```json
{
  "title": "美联储降息预期升温",
  "digest": "市场押注年内降息一次",
  "content_markdown": "...",
  "content_html": "...",
  "risk_level": "low",
  "style_score": 85
}
```

### 5.2 生成并发布

```bash
POST /api/v1/articles/publish
Content-Type: application/json

{
  "topic": "美联储降息预期"
}
```

### 5.3 查看定时任务

```bash
GET /api/v1/scheduler/status
```

**响应**:
```json
[
  {
    "id": "batch_finance_daily",
    "next_run_time": "2026-06-15 07:30:00",
    "trigger": "cron[hour='7', minute='30']"
  }
]
```

---

## 6. 故障排查

### 6.1 微信发布失败

**症状**: 上传草稿失败,报 `WechatAPIError`

**排查**:
1. 检查 `.env` 中 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`
2. 确认 `app/services/wechat/client.py` 中 `trust_env=False`
3. 检查网络连通性: `curl https://api.weixin.qq.com`
4. 查看日志: `grep WechatAPIError autowz.log`

**常见错误码**:
- `40001`: access_token 过期(自动重试)
- `40164`: IP 白名单问题(已通过 `trust_env=False` 解决)
- `45009`: 接口调用超过限额

### 6.2 定时任务不执行

**排查**:
1. 检查调度器状态: `curl http://localhost:8000/api/v1/scheduler/status`
2. 确认时区: `app/tasks/scheduler.py` 中 `timezone="Asia/Shanghai"`
3. 检查系统时间: `date`
4. 查看日志: `grep scheduler autowz.log`

### 6.3 LLM 调用失败

**排查**:
1. 检查 `.env` 中 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`
2. 测试连通性: `curl -H "Authorization: Bearer sk-XXX" <OPENAI_BASE_URL>/models`
3. 检查模型名称: `OPENAI_MODEL` 是否正确
4. 查看日志: `grep "LLM调用失败" autowz.log`

### 6.4 数据库连接失败

**排查**:
1. 检查 MySQL 服务: `systemctl status mysql`
2. 测试连接: `mysql -h localhost -u root -p autowz`
3. 检查 `.env` 中 `MYSQL_DSN`
4. 查看日志: `grep sqlalchemy autowz.log`

---

## 7. 最佳实践

### 7.1 开发新模块

1. **先设计 prompt**: 在 ChatGPT 等工具中测试 prompt 效果
2. **参考现有模块**: 复制 `finance/` 目录,修改配置和 prompt
3. **小步迭代**: 先实现基础功能,再优化细节
4. **验证效果**: 生成 10+ 篇测试文章,检查质量稳定性

### 7.2 Prompt 优化

1. **明确禁止项**: 列出具体的 AI 套话/机械表达
2. **给出示例**: 在 prompt 中给出正反对照
3. **结构化输出**: 要求固定格式(标题/摘要/正文分离)
4. **风格一致性**: 多次测试确保不同话题风格统一

### 7.3 生产部署

1. **使用 systemd**: 配置服务自动重启
2. **日志轮转**: 配置 logrotate 避免日志过大
3. **监控告警**: 接入 Sentry/Prometheus 监控异常
4. **定期备份**: 每周备份数据库
5. **灰度发布**: 新模块先手动测试 1 周再启用定时任务

### 7.4 内容质量保障

1. **人工抽检**: 每周抽查 5-10 篇文章
2. **用户反馈**: 关注微信后台留言和数据
3. **AB测试**: 同一话题生成 2 个版本,选质量更高的
4. **持续优化**: 每月根据反馈调整 prompt

---

## 8. 运营战略方案与可行性裁决(2026-06-18)

> 本章是运营**方向**的战略规划,与前 7 章的技术使用说明性质不同。
> 原标 `【待联网核实】` 的项,为 6-18 撰写时因 API 限流未能核准的数字/法规。
> **2026-06-19 更新**: `WebSearch`/`WebFetch` 持续 429,改用本机 `curl`(经代理)+ 搜狗网页检索完成核实,结论已回填各节,核实记录与残留待校准项见 8.8。

### 8.0 背景与目标

- **现状**: 公众号「现象观察」推荐量、阅读量近乎为 0。
- **用户目标**: 完全由 AI 自动运营维护,几乎不投入人力,日阅读 3000+。
- **已确认约束**: 多平台矩阵分发(算法平台起量、微信为最终目标号)/ 内容方向交由方案选最易起量垂类 / 尽量零成本(不投流)/ 目标口径为微信单号 3000+。

### 8.1 可行性裁决(最重要的真话)

**(1) "多平台 → 导流 → 喂微信"这条链是断的。**
今日头条、百家号、抖音等严禁站外导流,尤其严禁导流到微信(平台竞争红线)。内容里留微信号、二维码、"关注公众号 XX"会被限流、删文、扣分乃至封号。能渗透到微信的只有"同名品牌词"这种极弱自然转化。

> **核实(2026-06-19,搜狗)**: 头条《头条号平台关于规范推广类信息发布的公告》明确禁止推广微信/微博等第三方账号,违规扣分、禁言;抖音禁止私信添加私人微信引导交易;百家号《关于挂载恶意导流链接整治行动公示》打击挂链、禁留联系方式;微信侧《外部链接内容管理规范》对诱导分享最高可永久封号。**结论成立。**

**(2) "微信单号 + 零成本 + 纯 AI + 日阅读 3000"是所有口径里最硬的。**
微信订阅号无算法推荐,3000 阅读只能来自两处:
- **粉丝打开**: 行业平均打开率持续暴跌 —— 据 2026-06 公开文章引用,**2025 年 Q1 公众号平均打开率已低至约 0.89%**(八年跌超 90%;早年"10%"已是老黄历)。反推所需粉丝量:
  - 0.9%(2025 Q1 行业均值)→ 约需 **约 34 万粉**
  - 2%(显著高于均值)→ 约需 **15 万粉**
  - 5%(粘性不错的小号)→ 约需 **6 万粉**
  - 10%(高粘性"小而美")→ 约需 **3 万粉**
- **破圈**: 好友"在看"触发"看一看"二次推荐,可远超粉丝数,但需内容具备"社交货币",纯资讯搬运几乎无法触发。

零成本纯 AI 涨粉很慢,无爆款时月涨几百到几千粉。**结论: 死磕"微信单号 3000",现实周期 12 个月以上,且必须押注做出能进"看一看"的爆款。**

**(3) "完全不用人"不现实。** 见 8.6 最小人工清单。

### 8.2 核心建议: 松绑目标口径

建议把硬指标由「微信单号 3000」调整为:

> **全平台日总阅读先破 3000(3 个月内可达),微信号同步稳定爬坡,作为 12 个月级长期目标。**

理由: 用对新号友好的算法平台先跑出正反馈,避免被单一最难指标拖死。**(此项需用户拍板)**

### 8.3 内容方向: 放弃财经/娱乐资讯解读

财经/娱乐"资讯解读"是最差选择: 同质化、无收藏价值、无关注理由、无转发动力,且踩监管边(荐股/隐私谣言)。

改做 **"实用工具型知识"**,判据全中(算法平台爱推 / AI 易稳定生产 / 有关注理由可收藏 / 低监管风险 / 选题不枯竭)。优先级:

1. **AI 工具 / 效率 / 数码避坑**(首选)
2. **职场打工人实用指南**(留干货、去情绪宣泄)
3. **生活省钱 / 消费避坑**(财经降维到家庭层面,剥离荐股)

核心转变: 从"今天发生了什么"(资讯)→ "这事你该怎么做"(方法/工具)。

### 8.4 多平台矩阵的正确用法(既然不能导流)

- 头条号 / 百家号 / 视频号各自独立起量,统一用"现象观察"沉淀品牌词。
- **一鱼多吃**: 一个选题由 AI 自动产出适配各平台的版本。
- 微信合规涨粉只有三条腿:
  1. **搜一搜 SEO** —— 排名主因(2026-06-19 核实): **号名含关键词**(权重最高,约 25%)/ 微信认证 / 历史文章数与**被分享数** / 更新频率与质量 / 标题正文关键词匹配度。对应动作: 起一个含目标搜索词的号名、保持认证、稳定垂直更新、促分享
  2. **视频号** —— 唯一合规的"微信生态内导流引擎",可挂公众号,重点投入
  3. 内容尾部引导"在看/分享/收藏" + 冷启动期人工种子在看,搏"看一看"破圈

### 8.5 autowz 工程改造清单

| 优先级 | 改造项 | 说明 |
|---|---|---|
| **P0** | 数据回收闭环 | 现状是盲飞。自动拉取微信阅读/在看/涨粉 + 头条/百家阅读量,落库并生成周报。一切迭代的前提。 |
| **P0** | 内容重构 | prompt 与选题源从"热点资讯"换成选定垂类的"实用方法型"。 |
| **P0** | AIGC 合规标注 | **法律强制**: 四部门《人工智能生成合成内容标识办法》(国信办通字〔2025〕2号)已于 **2025-09-01 施行**,须加显式标识(内容起始/中间/末尾可感知的文字/图形提示)+ 隐式标识(文件元数据水印),平台并严查"伪原创"。不做即违法且被降权。 |
| **P1** | 多平台自动发布 | 核实(2026-06-19): 头条/百家/大鱼**无面向个人的官方开放 API**;业界靠第三方/开源"一键分发工具"(模拟登录 + cookie 的 RPA 类,支持头条/百家/大鱼/知乎等),**有开源工具可复用**。登录态会失效,需接受半自动(偶尔扫码重登)。 |
| **P1** | 搜一搜 SEO 模块 | 标题/关键词/摘要结构化优化。 |
| **P1** | 自动发布灰度闸 | 打开 `WECHAT_ENABLE_AUTO_PUBLISH`,但加风控闸 + 灰度,不裸奔。 |
| **P2** | 数据驱动自动选题 / AB | 数据闭环跑起来后,AI 按表现自动调选题与标题。 |

### 8.6 必须保留的"最小人工"

- 各平台注册 / 实名 / 活体认证(平台强制)
- 冷启动期种子"在看"(真人触发"看一看")
- 违规 / 限流申诉
- 每周 10 分钟看 AI 数据周报、拍方向

### 8.7 最高杠杆的 3 件事

1. **先建数据闭环** —— 结束盲飞。
2. **换垂类 + 内容从"资讯"转"实用"** —— 0 阅读的真正病根。
3. **All in 算法平台起量 + 视频号反哺微信** —— 放弃直接导流喂微信的幻想。

### 8.8 核实记录(2026-06-19,搜狗检索)

> `WebSearch`/`WebFetch` 持续 429,改用本机 `curl`(经代理)+ 搜狗网页检索完成核实(百度/Bing/DuckDuckGo 均被反爬拦截,仅搜狗可用)。以下结论已回填对应章节:

| # | 核实项 | 结论 | 回填位置 |
|---|---|---|---|
| 1 | 头条/百家/抖音 导流到微信处罚 | 普遍禁止站外导流,违规扣分/禁言/限流直至封号 | 8.1(1) |
| 2 | AIGC 标识办法 | 国信办通字〔2025〕2号,2025-09-01 施行,显式+隐式双标识 | 8.5 P0 |
| 3 | 微信订阅号打开率 | 2025 Q1 约 0.89%,八年跌超 90% | 8.1(2) |
| 4 | 搜一搜 SEO 排名因素 | 号名关键词(~25%)/认证/历史文章数/被分享数/更新/匹配度 | 8.4 |
| 5 | 头条/百家/大鱼 发布 API | 无个人官方 API,靠第三方/开源一键分发工具(RPA),有开源可复用 | 8.5 P1 |

**残留待校准**(搜狗结果时效混杂,宜后续用实时检索复核): 0.89% 打开率的原始出处与口径、各平台导流处罚的最新条款版本、开源一键分发工具的具体可用性与维护状态。

---

## 附录: 已废弃功能

以下功能在 Phase 1 重构中已移除:

- ❌ **Humanizer**: 双 LLM 叠加 AI 指纹,已合并到 Writer
- ❌ **"今天怎么看｜"前缀**: 固定标题模板,已删除
- ❌ **"(全文共X字)"**: 机器标识,已删除
- ❌ **每天3篇**: 改为每天1篇精品

旧代码已归档到 `.archive/deprecated/`。

---

**维护者**: Claude Code  
**最后更新**: 2026-06-19  
**相关文档**: README.md
