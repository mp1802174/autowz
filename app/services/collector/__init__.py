"""Topic collection services."""

from app.services.collector.base import BaseCollector, CollectedTopic
from app.services.collector.manager import CollectorManager
from app.services.collector.search import NewsCollector, NewsItem

__all__ = ["BaseCollector", "CollectedTopic", "CollectorManager", "NewsCollector", "NewsItem"]
