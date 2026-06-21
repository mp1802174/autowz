from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CollectedTopic:
    title: str
    source: str
    hot_score: float
    summary: str
    source_url: Optional[str] = None


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self) -> List[CollectedTopic]:
        """采集热点话题，返回按热度排序的列表。"""
