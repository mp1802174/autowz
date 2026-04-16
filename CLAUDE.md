# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**autowz**（《今天怎么看》微信公众号自动发布系统）— 自动抓取热点话题（微博+百度热搜）、LLM 生成评论文章、人味化改写、合规审核后发布到微信公众号"知微观澜"。Python 3.11+ / FastAPI / MySQL / APScheduler。

## 常用命令

```bash
# 安装（需要 Python 3.11+）
/root/.local/share/uv/python/cpython-3.11.15-linux-aarch64-gnu/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,db,worker]"

# 运行
uvicorn app.main:app --reload

# 初始化数据库
python scripts/init_db.py

# 测试
pytest tests/ -v

# 代码检查
ruff check app/

# Docker 本地环境（API + Redis + MySQL）
docker-compose up
```

## 架构

```
请求/定时触发 → ArticlePipeline 编排器
  ├── CollectorManager → 微博/百度热搜采集
  ├── TopicSelectorService → LLM 选题评分
  ├── WriterService → LLM 文章生成（短文冲突型/长文融合型）
  ├── HumanizerService → LLM 去AI味改写
  ├── GuardService → 关键词快筛 + LLM 风控审核
  └── WechatPublishOrchestrator → 发布编排
      ├── MaterialService → 封面上传
      ├── DraftService → 创建草稿
      └── PublishService → 提交发布 + 状态轮询
```

```
app/
├── main.py                        # FastAPI 入口 + lifespan（DB初始化 + 调度器）
├── core/config.py                 # Pydantic Settings（.env 配置）
├── core/logging.py                # 结构化日志配置
├── db/
│   ├── engine.py                  # SQLAlchemy engine + session
│   ├── models.py                  # ORM 模型（topics/articles/wechat_publish_records）
│   └── crud.py                    # CRUD 函数
├── api/routes/
│   ├── articles.py                # 文章相关 API
│   ├── scheduler.py               # 调度器状态 API
│   └── health.py                  # 健康检查
├── services/
│   ├── pipeline.py                # ArticlePipeline 核心编排器
│   ├── llm/client.py              # OpenAI 兼容 LLM 客户端（支持自定义 base_url）
│   ├── collector/{weibo,baidu,manager}.py  # 热点采集
│   ├── selector/service.py        # LLM 选题评分
│   ├── writer/service.py          # LLM 文章生成
│   ├── humanizer/service.py       # LLM 人味化改写
│   ├── guard/service.py           # 双层风控（关键词 + LLM）
│   └── wechat/                    # 微信公众号集成
│       ├── service.py             # 发布编排器（含 token 重试 + 降级）
│       ├── client.py              # HTTP 客户端（含 errcode 检查）
│       ├── cover_generator.py     # Pillow 封面图生成
│       └── {token,material,draft,publish}_service.py
└── tasks/scheduler.py             # APScheduler 定时任务
```

## API 端点

- `GET /health` — 健康检查
- `POST /api/v1/articles/preview` — 预览文章生成
- `POST /api/v1/articles/publish` — 完整发布流程
- `POST /api/v1/articles/collect` — 手动触发热点采集
- `GET /api/v1/articles/topics` — 今日话题列表
- `GET /api/v1/articles/{id}` — 文章详情
- `POST /api/v1/articles/batch/{type}` — 手动触发批次（morning/noon/evening）
- `GET /api/v1/scheduler/status` — 调度器状态
- `POST /api/v1/scheduler/trigger/{job_id}` — 手动触发定时任务

## 配置

通过 `.env` 文件管理（参考 `.env.example`）。关键配置项：
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` — LLM（支持 DeepSeek 等兼容 API）
- `WECHAT_APP_ID` / `WECHAT_APP_SECRET` — 公众号凭据
- `WECHAT_ENABLE_AUTO_PUBLISH` — 是否自动发布（false 则仅创建草稿）
- `MYSQL_DSN` — MySQL 连接字符串（默认通过 unix socket 连接本机）

## 数据库

MySQL 5.7，三张表：`topics`（热点话题）、`articles`（文章）、`wechat_publish_records`（发布记录）。ORM 模型在 `app/db/models.py`，CRUD 在 `app/db/crud.py`。

## 代码规范

- Ruff：line-length=100，target-version=py311
- 全异步（async/await），httpx 作为 HTTP 客户端
- Pydantic v2 用于数据校验
- 中文项目，代码注释和文档以中文为主
- f-string 中避免使用中文引号（会导致语法错误），用方括号替代
