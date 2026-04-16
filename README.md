# autowz -《今天怎么看》微信公众号自动发布系统

自动抓取热点话题（微博 + 百度热搜）、LLM 生成评论文章、人味化改写、合规审核后发布到微信公众号"知微观澜"。

## 系统要求

- Python 3.11+
- MySQL 5.7+
- Redis（可选，当前未强依赖）

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境（使用 Python 3.11+）
python3.11 -m venv .venv
source .venv/bin/activate

# 安装所有依赖
pip install -e ".[dev,db,worker]"
```

### 2. 配置环境变量

复制 `.env.example` 并填写实际配置：

```bash
cp .env.example .env
```

需要修改的关键配置：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `OPENAI_API_KEY` | LLM API 密钥 | `sk-xxx` |
| `OPENAI_BASE_URL` | LLM API 地址（支持 DeepSeek 等兼容接口） | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 使用的模型名称 | `deepseek-v3p2` |
| `WECHAT_APP_ID` | 微信公众号 AppID | `wx...` |
| `WECHAT_APP_SECRET` | 微信公众号 AppSecret | `ae...` |
| `WECHAT_ENABLE_AUTO_PUBLISH` | 是否自动发布（`false` 则仅创建草稿） | `false` |
| `MYSQL_DSN` | MySQL 连接字符串 | `mysql+pymysql://root:pwd@localhost:3306/autowz?charset=utf8mb4` |

### 3. 初始化数据库

```bash
# 先在 MySQL 中创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS autowz CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"

# 运行建表脚本
python scripts/init_db.py
```

### 4. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后系统会自动：
- 初始化数据库连接
- 启动 APScheduler 定时任务调度器

## 日常使用

### 自动模式（推荐）

服务启动后，定时任务会自动执行：

| 任务 | 时间 | 说明 |
|------|------|------|
| 热点采集 | 每 30 分钟 | 抓取微博 + 百度热搜，去重后存入数据库 |
| 早间批次 | 每天 07:05 | 生成 1 篇短文（冲突型，600-800 字） |
| 午间批次 | 每天 12:05 | 生成 1 篇短文（冲突型，600-800 字） |
| 晚间批次 | 每天 18:35 | 生成 1 篇长文（融合型，800-1200 字） |

每篇文章会经历完整链路：**LLM 选题 → LLM 生成 → LLM 人味化改写 → 双层风控审核 → 微信发布/存草稿**

质量门控：`style_score < 80` 的文章不会发布。

### 手动操作

也可以通过 API 手动触发各环节：

#### 采集热点话题
```bash
curl -X POST http://localhost:8000/api/v1/articles/collect
```

#### 查看今日话题
```bash
curl http://localhost:8000/api/v1/articles/topics
```

#### 预览文章（不发布，仅生成预览）
```bash
curl -X POST http://localhost:8000/api/v1/articles/preview \
  -H "Content-Type: application/json" \
  -d '{"topic": "你想评论的话题", "article_type": "short"}'
```

`article_type` 可选 `short`（短文冲突型）或 `long`（长文融合型）。

#### 手动触发批次生成 + 发布
```bash
# morning = 短文, noon = 短文, evening = 长文
curl -X POST http://localhost:8000/api/v1/articles/batch/morning
curl -X POST http://localhost:8000/api/v1/articles/batch/noon
curl -X POST http://localhost:8000/api/v1/articles/batch/evening
```

#### 查看文章详情
```bash
curl http://localhost:8000/api/v1/articles/1
```

#### 查看调度器状态
```bash
curl http://localhost:8000/api/v1/scheduler/status
```

#### 手动触发定时任务
```bash
curl -X POST http://localhost:8000/api/v1/scheduler/trigger/collect_hot_topics
curl -X POST http://localhost:8000/api/v1/scheduler/trigger/morning_batch
```

#### 完整发布流程（指定话题直接发布）
```bash
curl -X POST http://localhost:8000/api/v1/articles/publish \
  -H "Content-Type: application/json" \
  -d '{"topic": "话题内容", "article_type": "short"}'
```

#### 健康检查
```bash
curl http://localhost:8000/health
```

## 文章生成流程

```
热点采集（微博+百度）
    ↓
LLM 选题评分（热度/争议性/评论空间/安全性/调性匹配）
    ↓
LLM 文章生成（"知微观澜"人设，短文冲突型/长文融合型）
    ↓
LLM 人味化改写（打散模板句式、增加口语化、注入个人判断语气等）
    ↓
双层风控审核（关键词快筛 + LLM 深度审核）
    ↓ 风险等级 low 才放行
微信发布（上传封面 → 创建草稿 → 提交发布）
```

## 微信发布模式

通过 `.env` 中的 `WECHAT_ENABLE_AUTO_PUBLISH` 控制：

- **`false`（默认）**：仅创建草稿到公众号草稿箱，需要手动登录公众号后台点击发布
- **`true`**：自动提交发布，文章会直接推送给关注者

建议初期使用 `false`，确认文章质量后再改为 `true`。

## 开发相关

```bash
# 运行测试
pytest tests/ -v

# 代码检查
ruff check app/

# Docker 本地环境
docker-compose up
```

## 目录结构

```
app/
├── main.py                          # FastAPI 入口 + lifespan
├── core/
│   ├── config.py                    # 配置管理（.env）
│   └── logging.py                   # 日志配置
├── db/
│   ├── engine.py                    # SQLAlchemy 引擎
│   ├── models.py                    # ORM 模型（topics/articles/wechat_publish_records）
│   └── crud.py                      # CRUD 操作
├── api/routes/
│   ├── articles.py                  # 文章 API
│   ├── scheduler.py                 # 调度器 API
│   └── health.py                    # 健康检查
├── services/
│   ├── pipeline.py                  # 核心编排器
│   ├── llm/client.py                # LLM 客户端
│   ├── collector/                   # 热点采集（微博+百度）
│   ├── selector/service.py          # LLM 选题评分
│   ├── writer/service.py            # LLM 文章生成
│   ├── humanizer/service.py         # LLM 人味化改写
│   ├── guard/service.py             # 双层风控审核
│   └── wechat/                      # 微信公众号发布
├── tasks/scheduler.py               # APScheduler 定时任务
scripts/
└── init_db.py                       # 数据库初始化脚本
```
