from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class CollectedTopic:
    title: str
    source: str
    hot_score: float
    summary: str
    source_url: str | None = None


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self) -> list[CollectedTopic]:
        """采集热点话题，返回按热度排序的列表。"""
