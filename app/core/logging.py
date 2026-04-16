import logging
import sys

from app.core.config import get_settings


def setup_logging() -> None:
    """配置应用日志。dev 环境使用可读格式，prod 使用 JSON 格式。"""
    settings = get_settings()
    level = logging.DEBUG if settings.app_debug else logging.INFO

    if settings.app_env == "prod":
        fmt = '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root_logger = logging.getLogger("autowz")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    root_logger.propagate = False

    # 降低第三方库日志级别
    for noisy in ("httpx", "openai", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
