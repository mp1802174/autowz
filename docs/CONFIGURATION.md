# 配置说明

项目主要通过 `.env` 管理配置，由 `app/core/config.py` 的 `Settings` 读取。图片生成 provider 通过 JSON 文件管理。

## `.env` / `Settings` 映射

| 环境变量 | Settings 字段 | 默认值/示例 | 说明 |
|---|---|---|---|
| `APP_NAME` | `app_name` | `autowz` | 应用名称。 |
| `APP_ENV` | `app_env` | `dev` | 环境，`prod` 时日志格式为 JSON。 |
| `APP_DEBUG` | `app_debug` | `true` | 调试模式，影响日志级别和 SQL echo。 |
| `API_PREFIX` | `api_prefix` | `/api/v1` | API 路由前缀。 |
| `CONTENT_AUTHOR` | `content_author` | `知微观澜` | 微信文章作者。 |
| `DEFAULT_COMMENT_OPEN` | `default_comment_open` | `1` | 微信评论开关。 |
| `DEFAULT_FANS_COMMENT_ONLY` | `default_fans_comment_only` | `0` | 是否仅粉丝评论。 |
| `WECHAT_APP_ID` | `wechat_app_id` | - | 公众号 AppID，敏感。 |
| `WECHAT_APP_SECRET` | `wechat_app_secret` | - | 公众号 AppSecret，敏感。 |
| `WECHAT_BASE_URL` | `wechat_base_url` | `https://api.weixin.qq.com` | 微信 API base URL。 |
| `WECHAT_ENABLE_AUTO_PUBLISH` | `wechat_enable_auto_publish` | `false` | 是否自动提交发布；false 只创建草稿。 |
| `WECHAT_FALLBACK_TO_DRAFT` | `wechat_fallback_to_draft` | `true` | 发布失败时是否保留/降级为草稿。 |
| `TIANAPI_KEY` | `tianapi_key` | - | 天行 API key；为空则跳过天行 API。 |
| `IMAGE_PROVIDERS_FILE` | `image_providers_file` | `image_providers.json` | 图片 provider 配置文件路径。 |
| `OPENAI_API_KEY` | `openai_api_key` | - | OpenAI 兼容 LLM API key，敏感。 |
| `OPENAI_BASE_URL` | `openai_base_url` | `https://api.openai.com/v1` | LLM API base URL。 |
| `OPENAI_MODEL` | `openai_model` | `gpt-5.4` | 默认模型名。 |
| `REDIS_URL` | `redis_url` | `redis://localhost:6379/0` | Redis 地址；当前未强依赖。 |
| `MYSQL_DSN` | `mysql_dsn` | MySQL DSN | SQLAlchemy 连接字符串，可能含密码，敏感。 |
| `MYSQL_POOL_SIZE` | `mysql_pool_size` | `5` | 连接池大小。 |
| `MYSQL_POOL_RECYCLE` | `mysql_pool_recycle` | `3600` | 连接回收秒数。 |

## 图片 provider 配置

示例文件：`image_providers.example.json`  
真实文件：`image_providers.json`，可能含 API key，默认不要展示。

每个 provider：

```json
{
  "name": "openai-compatible",
  "api_url": "https://api.example.com/v1/images/generations",
  "api_key": "***",
  "models": ["gpt-image-1"],
  "proxy": "",
  "enabled": true
}
```

代码读取位置：`app/services/wechat/cover_generator.py::_build_image_providers()`。

特点：

- 一个 provider 可配置多个 model，代码会展开为多个候选。
- 按 JSON 数组和 models 顺序依次尝试。
- 支持 provider 级代理。
- 兼容 `/images/generations` 和部分 `/chat/completions` 网关。

## 微信发布模式

| 配置组合 | 行为 |
|---|---|
| `WECHAT_ENABLE_AUTO_PUBLISH=false` | 上传封面、创建草稿，不提交发布。推荐默认。 |
| `WECHAT_ENABLE_AUTO_PUBLISH=true` | 创建草稿后调用 freepublish 提交，并轮询结果。 |
| `WECHAT_FALLBACK_TO_DRAFT=true` | 发布失败时尽量保留草稿并返回 draft_only/fallback 状态。 |
| 未配置 AppID/Secret | `WechatTokenService` 返回 mock token，上传/草稿/发布走 mock。 |

## 数据库配置

`MYSQL_DSN` 示例：

```text
mysql+pymysql://root:password@localhost:3306/autowz?charset=utf8mb4
```

或 Unix socket：

```text
mysql+pymysql://root:password@localhost:3306/autowz?charset=utf8mb4&unix_socket=/tmp/mysql.sock
```

数据库初始化：

```bash
python scripts/init_db.py
```

注意：当前没有迁移框架，`init_db()` 只创建不存在的表，不会修改已有表结构。

## 新增配置字段步骤

1. 在 `app/core/config.py::Settings` 添加字段、alias 和安全默认值。
2. 更新 `.env.example`。
3. 在业务代码通过 `get_settings()` 读取。
4. 更新 `docs/CONFIGURATION.md`。
5. 如果影响 Docker，更新 `docker-compose.yml`。
6. 添加或调整测试。

## 敏感信息规则

- `.env`、`.env.bak.*`、`image_providers.json` 不要写入文档内容。
- 日志中不要打印 API key、AppSecret、cookie、token、完整数据库密码。
- 文档示例统一使用 `your-xxx` 或 `***`。
