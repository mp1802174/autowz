from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="autowz", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    active_module: str = Field(default="entertainment", alias="ACTIVE_MODULE")

    content_author: str = Field(default="", alias="CONTENT_AUTHOR")  # 改为空,不显示作者名
    default_comment_open: int = Field(default=1, alias="DEFAULT_COMMENT_OPEN")
    default_fans_comment_only: int = Field(default=0, alias="DEFAULT_FANS_COMMENT_ONLY")

    wechat_app_id: str = Field(default="", alias="WECHAT_APP_ID")
    wechat_app_secret: str = Field(default="", alias="WECHAT_APP_SECRET")
    wechat_base_url: str = Field(default="https://api.weixin.qq.com", alias="WECHAT_BASE_URL")
    wechat_enable_auto_publish: bool = Field(default=False, alias="WECHAT_ENABLE_AUTO_PUBLISH")
    wechat_fallback_to_draft: bool = Field(default=True, alias="WECHAT_FALLBACK_TO_DRAFT")

    tianapi_key: str = Field(default="", alias="TIANAPI_KEY")

    # 选题时传给 LLM 排序的候选新闻上限（去重聚类后池子已变小）
    selector_llm_max_items: int = Field(default=50, alias="SELECTOR_LLM_MAX_ITEMS")

    image_providers_file: str = Field(
        default="image_providers.json",
        alias="IMAGE_PROVIDERS_FILE",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-5.4", alias="OPENAI_MODEL")

    # LLM fallback 模型列表(按优先级排序)
    llm_fallback_models: str = Field(
        default="claude-opus-4-6,claude-sonnet-4-6,deepseek-v4-pro,kimi-k2.6,kimi-k2p5,gpt-oss-120b,google/gemma-4-31b-it",
        alias="LLM_FALLBACK_MODELS",
    )

    publish_targets: str = Field(default="wechat", alias="PUBLISH_TARGETS")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    mysql_dsn: str = Field(
        default="mysql+pymysql://root:1c8034bf4061cbd6@localhost:3306/autowz?charset=utf8mb4&unix_socket=/tmp/mysql.sock",
        alias="MYSQL_DSN",
    )
    mysql_pool_size: int = Field(default=5, alias="MYSQL_POOL_SIZE")
    mysql_pool_recycle: int = Field(default=3600, alias="MYSQL_POOL_RECYCLE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
