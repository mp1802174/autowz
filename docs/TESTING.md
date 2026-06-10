# 测试与验证指南

## 推荐基础检查

```bash
pytest tests/ -v
ruff check app tests scripts
python -m py_compile $(find app scripts tests -name '*.py' -not -path '*/__pycache__/*')
```

## 按修改范围验证

| 修改范围 | 建议验证 |
|---|---|
| API 路由 | `pytest tests/test_health.py -v`，必要时用 TestClient 新增测试。 |
| 文章预览 pipeline | `pytest tests/test_pipeline.py -v`，mock LLM/搜索/微信。 |
| 采集器去重 | `pytest tests/test_collector.py -v`。 |
| 选题 fallback/优先级 | `pytest tests/test_selector.py -v`。 |
| 风控词库 | `pytest tests/test_guard.py -v`。 |
| 字数控制 | `pytest tests/test_content_length.py -v`。 |
| 配置 | `python - <<'PY'\nfrom app.core.config import get_settings; print(get_settings().app_name)\nPY`。 |
| 数据库模型 | 本地测试库运行 `python scripts/init_db.py`；生产库需迁移计划。 |
| 封面图 provider | `python scripts/test_image_providers.py --timeout 90`，但需用户确认。 |
| 微信发布 | 优先 mock；真实发布/草稿需用户确认。 |

## 本地服务健康检查

如果服务已启动：

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/scheduler/status
```

## 不要自动执行的高副作用命令/API

除非用户明确要求，不要自动执行：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
python scripts/test_image_providers.py
python scripts/generate_avatar.py
```

以及这些 API：

```bash
curl -X POST http://localhost:8000/api/v1/articles/publish ...
curl -X POST http://localhost:8000/api/v1/articles/batch/morning
curl -X POST http://localhost:8000/api/v1/articles/batch/noon
curl -X POST http://localhost:8000/api/v1/articles/batch/evening
curl -X POST http://localhost:8000/api/v1/scheduler/trigger/sync_published_articles
```

原因：可能调用真实 LLM、真实图片生成、真实微信草稿/发布、读取微信后台 cookie 或消耗 API 额度。

## 更新 AI 自动索引

当新增/删除较多文件或调整模块职责后，运行：

```bash
python scripts/update_ai_docs_index.py
```

这会刷新：

```text
docs/AUTO_PROJECT_INDEX.md
```
