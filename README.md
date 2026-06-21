# autowz - 智能多渠道文章自动草稿系统

> 自动采集热点、LLM 生成高质量文章，并保存到微信 / 头条 / 百家号草稿箱，人工审核后发布。

**当前状态**: ✅ 生产就绪  
**版本**: v2.0 (模块化架构)  
**最后更新**: 2026-06-21

---

## 🚨 项目第一纲领(生存底线,不可违背)

> **质量第一,质量低不如不做。** 这是本项目凌驾一切的最高纲领,换任何开发者 / 维护者 / AI 都必须第一时间遵循。

- **生存前提**:产出「有真实信息增量、读起来不像机器」的高质量内容;宁可少发、不发,**绝不发低质**。
- **走质量路线,不走规避路线**:目标是「标注 AI 也不掉流量、被检测也不算低质」,而非靠隐藏 AI / 洗稿赌平台查不到。
- **唯一判据**:任何改动先问一句 —— 它提升了内容质量,还是为数量 / 效率 / 规避牺牲了质量?后者不做。
- **依据**:平台降权的真正触发器是「AI 痕迹 + 低质」,而非「是否声明 AI」(详见 [GUIDE.md](GUIDE.md) §8)。

---

## 🎯 项目特点

### 核心能力
- 📊 **数据驱动解读**: 不做新闻搬运,专注数据分析与趋势判断
- 🤖 **全流程自动化**: 采集→选题→生成→审核→发布,无需人工干预
- 🧩 **模块化架构**: 支持财经/娱乐/视频等多种内容类型,独立配置
- 🛡️ **风控保障**: 关键词拦截、内容审核、多级风险判定
- 📈 **微信优化**: 去除AI指纹,符合微信原创要求,提升推荐量

### 与传统方案的区别
| 传统AI公众号 | autowz |
|-------------|--------|
| 复述新闻,高相似度 | 数据解读,独家整合 |
| 双LLM叠加,AI味重 | 单次生成,风格自然 |
| "(全文共X字)"机器标识 | 无机器指纹 |
| 固定模板,内容同质 | 签名结构,难复刻 |
| 单一内容类型 | 模块化,可扩展财经/娱乐/视频 |

---

## 🚀 快速开始

### 1. 环境要求
- Python 3.9+
- MySQL 8.0+
- Redis(可选)

### 2. 安装
```bash
git clone <repo-url> autowz
cd autowz

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入微信公众号 AppID/Secret、LLM API Key 等
```

### 3. 数据库初始化
```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE autowz CHARACTER SET utf8mb4;"

# 运行迁移(如果有 alembic)
alembic upgrade head

# 或导入初始 schema
mysql -u root -p autowz < schema.sql
```

### 4. 启动系统
```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式(后台运行)
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > autowz.log 2>&1 &
```

### 5. 验证
```bash
# 检查API
curl http://localhost:8000/api/v1/health

# 手动生成测试文章
curl -X POST http://localhost:8000/api/v1/articles/preview \
  -H "Content-Type: application/json" \
  -d '{"topic": "测试话题"}'
```

---

## 📦 核心功能

### 1. 自动发布(定时任务)
- **当前生产模块**: `ACTIVE_MODULE=entertainment`，每天 16:20 生成 1 篇
- **当前发布目标**: `PUBLISH_TARGETS=wechat,toutiao,baijiahao`
- **发布策略**: 三渠道均只保存草稿，审核后人工发布；不允许自动正式发布
- **可配置**: 在各模块 `config.py` 的 `SCHEDULE_SLOTS` 中修改时间/频率
- **维护记录**: 关键变更与坑位见 `docs/maintenance_notes.md`

### 2. 手动发布(API)
```bash
# 预览文章(不发布)
POST /api/v1/articles/preview
{
  "topic": "美联储降息预期",
  "stance": "谨慎观望"  # 可选
}

# 生成并保存草稿
POST /api/v1/articles/publish
{
  "topic": "美联储降息预期"
}
```

### 3. 模块切换
```python
from app.services.pipeline import ArticlePipeline

# 财经模块
pipeline = ArticlePipeline("finance")
await pipeline.run_batch("morning", count=1)

# 娱乐模块
pipeline = ArticlePipeline("entertainment")
```

---

## 🧩 模块化架构

### 当前模块
- ✅ **财经模块** (`finance`): 数据驱动解读型,每天 7:30 发 1 篇
- ✅ **娱乐模块** (`entertainment`): 影视/明星/综艺评论,当前生产启用,每天 16:20 发 1 篇草稿

### 如何新增模块
完整步骤见 `GUIDE.md → 模块扩展指南`

简化流程:
1. 创建 `app/modules/<模块名>/`
2. 实现 `config.py` + `writer.py` + `module.py`
3. 在 `app/modules/registry.py` 注册
4. 在 `app/tasks/scheduler.py` 配置定时任务

---

## 📊 数据流

```
天行API/RSS/搜狗新闻
    ↓ 采集
新闻池(200-300条)
    ↓ LLM选题(优先财经关键词)
精选话题(1-3个)
    ↓ 搜狗详情搜索(8条)
素材整合
    ↓ DataDrivenWriter(单次生成,数据解读型)
文章草稿(650-750字)
    ↓ GuardService风控审核
通过审核
    ↓ 生成封面
标准文章产物
    ↓ 渠道适配
微信: 追加「精彩文章导读」+ 封面/正文图 → 草稿
头条/百家: 剥离导读 + 上传封面/正文图 → 草稿
✅ 三渠道草稿完成，人工审核后发布
```

---

## 🛠️ 配置说明

### 环境变量(.env)
```bash
# 微信公众号
WECHAT_APP_ID=wxXXXXXX
WECHAT_APP_SECRET=XXXXXX

# LLM(OpenAI兼容接口)
OPENAI_API_KEY=sk-XXXX
OPENAI_BASE_URL=https://your-api.com/v1
OPENAI_MODEL=gpt-4

# 新闻API
TIANAPI_KEY=XXXX

# 数据库
MYSQL_DSN=mysql+pymysql://user:pass@localhost:3306/autowz
```

### 模块配置
每个模块独立配置,互不影响:
```python
# app/modules/finance/config.py
MODULE_NAME = "finance"
AUTHOR = "现象观察"

SCHEDULE_SLOTS = [
    ScheduleSlot(hour=7, minute=30, batch_type="daily", count=1),
]

WRITER_CONFIG = {
    "min_chars": 650,
    "max_chars": 750,
    "style": "data_driven_analysis",
}
```

---

## 📁 项目结构

```
autowz/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── core/                # 核心配置
│   ├── db/                  # 数据库模型
│   ├── models/              # Pydantic schemas
│   ├── api/                 # API 路由
│   ├── tasks/               # 定时任务
│   │   └── scheduler.py     # 定时调度器
│   ├── services/            # 基础服务
│   │   ├── collector/       # 新闻采集
│   │   ├── selector/        # LLM 选题
│   │   ├── guard/           # 风控审核
│   │   ├── wechat/          # 微信发布
│   │   └── llm/             # LLM 客户端
│   └── modules/             # 🔥 模块化架构
│       ├── base.py          # 抽象基类
│       ├── registry.py      # 模块注册表
│       └── finance/         # 财经模块
│           ├── config.py
│           ├── writer.py
│           └── module.py
├── .env                     # 环境变量
├── requirements.txt         # 依赖
├── README.md               # 本文件
└── GUIDE.md                # 完整使用指南
```

---

## 🔍 关键文件速查

| 文件 | 用途 | 何时修改 |
|------|------|----------|
| `.env` | 环境变量 | 部署时配置密钥 |
| `app/tasks/scheduler.py` | 定时任务 | 修改发布时间/频率 |
| `app/modules/finance/config.py` | 财经模块配置 | 修改作者/字数/风格 |
| `app/modules/finance/writer.py` | 写作器 | 修改 prompt/风格 |
| `app/modules/registry.py` | 模块注册 | 新增模块时注册 |

---

## 📈 生产运维

### 查看日志
```bash
# 实时日志
tail -f autowz.log

# 过滤错误
grep ERROR autowz.log

# 查看定时任务
curl http://localhost:8000/api/v1/scheduler/status
```

### 数据库维护
```bash
# 查看最近文章
mysql autowz -e "SELECT id, title, status, created_at FROM articles ORDER BY id DESC LIMIT 10;"

# 查看发布记录
mysql autowz -e "SELECT * FROM wechat_publish_records ORDER BY id DESC LIMIT 5;"

# 清理旧数据(30天前)
mysql autowz -e "DELETE FROM articles WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);"
```

### 健康检查
```bash
# 系统状态
curl http://localhost:8000/api/v1/health

# 定时任务状态
curl http://localhost:8000/api/v1/scheduler/status

# 微信 API 连通性(会消耗 access_token 配额,慎用)
# curl http://localhost:8000/api/v1/wechat/test
```

---

## 🐛 常见问题

### Q1: 文章被判"低创作度"?
A: 已在 Phase 1 解决,检查:
- ✅ 结尾无"(全文共X字)"
- ✅ 标题无"今天怎么看｜"
- ✅ 单次生成(未双 LLM)
- ✅ 使用数据解读型 prompt

### Q2: 微信发布失败?
A: 检查:
1. `.env` 中 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET` 正确
2. 确保 `app/services/wechat/client.py` 中 `trust_env=False`(不走代理)
3. 查看日志具体错误信息

### Q3: 定时任务不执行?
A: 检查:
1. `app/tasks/scheduler.py` 中任务是否启用
2. 时区是否正确(Asia/Shanghai)
3. 系统时间是否准确

### Q4: Markdown 表格不显示?
A: 已修复,确保 `app/modules/finance/writer.py` 中:
```python
content_html = md_lib.markdown(content_md, extensions=['tables'])
```

### Q5: 如何新增娱乐模块?
A: 见 `GUIDE.md → 模块扩展指南 → 新增娱乐模块`

---

## 📚 进阶阅读

- **`GUIDE.md`** - 完整使用指南(模块化设计、配置详解、扩展开发)
- **`app/modules/finance/writer.py`** - 数据解读型 writer 实现(含完整 prompt)
- **`app/tasks/scheduler.py`** - 定时任务配置
- **`.archive/`** - 历史文档归档(参考用)

---

## 🤝 贡献

本项目由 Claude Code 开发,欢迎提交 Issue 和 PR。

---

## 📄 许可

[根据实际情况填写]

---

**最后更新**: 2026-06-14  
**维护者**: Claude Code  
**项目状态**: ✅ 生产就绪
