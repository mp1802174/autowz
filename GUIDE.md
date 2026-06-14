# GUIDE - autowz 完整使用指南

**版本**: v2.0  
**更新时间**: 2026-06-14

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

# 娱乐模块(需先实现)
pipeline = ArticlePipeline("entertainment")
await pipeline.run_batch("afternoon", 1)
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
    "style": "data_driven_analysis",
    "structure": "hook-data-analysis-impact-conclusion",
}

# 调度配置
SCHEDULE_CONFIG = {
    "enabled": True,
    "cron_hour": 7,
    "cron_minute": 30,
    "daily_count": 1,
}
```

### 2.3 定时任务配置

在 `app/tasks/scheduler.py` 中配置:

```python
# 财经模块: 每天早上 7:30
scheduler.add_job(
    _job_batch,
    CronTrigger(hour=7, minute=30),
    args=["morning", 1, "finance"],
    id="finance_daily_batch",
)

# 娱乐模块: 每天下午 13:00(需先实现)
# scheduler.add_job(
#     _job_batch,
#     CronTrigger(hour=13, minute=0),
#     args=["entertainment", 1],
#     id="entertainment_daily_batch",
# )
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

SCHEDULE_CONFIG = {
    "enabled": True,
    "cron_hour": 13,
    "cron_minute": 0,
    "daily_count": 1,
}
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
    "id": "finance_daily_batch",
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

## 附录: 已废弃功能

以下功能在 Phase 1 重构中已移除:

- ❌ **Humanizer**: 双 LLM 叠加 AI 指纹,已合并到 Writer
- ❌ **"今天怎么看｜"前缀**: 固定标题模板,已删除
- ❌ **"(全文共X字)"**: 机器标识,已删除
- ❌ **每天3篇**: 改为每天1篇精品

旧代码已归档到 `.archive/deprecated/`。

---

**维护者**: Claude Code  
**最后更新**: 2026-06-14  
**相关文档**: README.md
