"""模块注册表

所有内容模块的注册中心。新增模块时在这里注册即可。
"""

from typing import Dict, Type

from app.modules.base import BaseContentModule


# 延迟导入,避免循环依赖
def _get_finance_module():
    from app.modules.finance.module import FinanceModule
    return FinanceModule


# 模块注册表
MODULE_REGISTRY: Dict[str, Type[BaseContentModule]] = {
    "finance": _get_finance_module,
    # 未来扩展:
    # "entertainment": _get_entertainment_module,
    # "video": _get_video_module,
}


def get_module(name: str) -> BaseContentModule:
    """根据模块名获取模块实例

    Args:
        name: 模块名(如 'finance', 'entertainment')

    Returns:
        模块实例

    Raises:
        KeyError: 模块不存在
    """
    if name not in MODULE_REGISTRY:
        raise KeyError(f"模块 '{name}' 不存在,可用模块: {list(MODULE_REGISTRY.keys())}")

    module_class = MODULE_REGISTRY[name]
    if callable(module_class):
        # 延迟导入的工厂函数
        module_class = module_class()
    return module_class()


def list_modules() -> list[str]:
    """列出所有已注册模块"""
    return list(MODULE_REGISTRY.keys())
