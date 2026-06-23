"""内容质量校验包。

# ⚠️ 项目第一纲领(不可违背):质量第一,质量低不如不做。
#    本包是「质量防线」的核心:在文章入库 / 发布前,拦下退化、断头、
#    重复、注水等低质产物。宁可弃稿不发,也不让低质内容进入草稿箱。
"""

from app.services.quality.checker import (
    ContentQualityError,
    QualityResult,
    check_quality,
)

__all__ = ["ContentQualityError", "QualityResult", "check_quality"]
