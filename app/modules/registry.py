"""内容模块注册表。"""

from collections.abc import Callable

from app.core.config import get_settings
from app.modules.base import BaseContentModule
from typing import Dict, List, Optional

ModuleFactory = Callable[[], type[BaseContentModule]]


def _get_finance_module() -> type[BaseContentModule]:
    from app.modules.finance.module import FinanceModule
    return FinanceModule


def _get_entertainment_module() -> type[BaseContentModule]:
    from app.modules.entertainment.module import EntertainmentModule
    return EntertainmentModule


MODULE_REGISTRY: Dict[str, ModuleFactory] = {
    "finance": _get_finance_module,
    "entertainment": _get_entertainment_module,
}


def list_modules() -> List[str]:
    """列出所有已注册模块。"""
    return list(MODULE_REGISTRY.keys())


def resolve_module_name(name: Optional[str] = None) -> str:
    """解析模块名。

    name 为 None 时读取 ACTIVE_MODULE；默认值在配置里是 entertainment。
    写错模块名直接报错，避免静默跑错模块。
    """
    module_name = (name or get_settings().active_module or "finance").strip().lower()
    if module_name not in MODULE_REGISTRY:
        available = ", ".join(list_modules())
        raise ValueError(f"未知内容模块: {module_name}. 可用模块: {available}")
    return module_name


def get_module(name: Optional[str] = None) -> BaseContentModule:
    """根据模块名获取模块实例；name=None 时使用 ACTIVE_MODULE。"""
    module_name = resolve_module_name(name)
    module_class = MODULE_REGISTRY[module_name]()
    return module_class()
