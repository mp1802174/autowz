"""
定时同步：从微信公众平台后台拉取「现象观察」已发布文章列表，
按标题精确匹配 articles 表，回填 article_url 到 wechat_publish_records，
状态置为 success。后续导读区块即可从中随机挑文章。
"""

import logging

from app.db.engine import get_db_session
from app.db.models import Article, WechatPublishRecord
from app.services.wechat.mp_backend import (
    MpBackendAuthExpired,
    MpBackendError,
    WechatMpBackend,
)

logger = logging.getLogger("autowz.wechat.publish_sync")


async def sync_published_articles(
    limit: int = 200,
) -> dict:
    """
    以"当前登录账号管理员"视角拉自家公众号全部已发表文章，
    按 title 精确匹配 articles 表回填 article_url 和 success 状态。

    返回: {fetched, matched, updated, inserted, skipped_no_article, auth_expired}
    """
    backend = WechatMpBackend()

    try:
        published = await backend.list_published_articles(account_name=None, limit=limit)
    except MpBackendAuthExpired as exc:
        logger.error("登录凭据已过期，请到 newwz 重新扫码：%s", exc)
        return {"auth_expired": True, "error": str(exc), "fetched": 0}
    except MpBackendError as exc:
        logger.error("拉取已发布列表失败：%s", exc)
        return {"error": str(exc), "fetched": 0}

    logger.info("从公众号后台拉到 %d 条已发表文章", len(published))

    matched = updated = inserted = skipped = 0

    with get_db_session() as session:
        for pub in published:
            title = pub["title"]
            url = pub["article_url"]
            if not title or not url:
                continue

            article = (
                session.query(Article)
                .filter(Article.title == title)
                .order_by(Article.id.desc())
                .first()
            )
            if not article:
                skipped += 1
                logger.debug("articles 表无匹配标题，跳过: %s", title)
                continue

            matched += 1
            existing = (
                session.query(WechatPublishRecord)
                .filter(WechatPublishRecord.article_id == article.id)
                .order_by(WechatPublishRecord.id.desc())
                .first()
            )

            if existing:
                if (
                    existing.publish_status == "success"
                    and existing.article_url == url
                ):
                    continue
                existing.publish_status = "success"
                existing.article_url = url
                if not existing.raw_response:
                    existing.raw_response = {}
                existing.raw_response = {
                    **(existing.raw_response or {}),
                    "synced_from_mp_backend": True,
                    "synced_aid": pub.get("aid"),
                    "synced_cover": pub.get("cover"),
                }
                updated += 1
                logger.info("回填 article_id=%s url=%s", article.id, url[:60])
            else:
                session.add(
                    WechatPublishRecord(
                        article_id=article.id,
                        draft_media_id="",
                        publish_id="",
                        article_url=url,
                        publish_status="success",
                        raw_response={
                            "synced_from_mp_backend": True,
                            "synced_aid": pub.get("aid"),
                            "synced_cover": pub.get("cover"),
                        },
                        cover_media_id="",
                    )
                )
                inserted += 1
                logger.info("新增同步记录 article_id=%s url=%s", article.id, url[:60])

            if article.status != "published":
                article.status = "published"
                article.published_at = pub["publish_at"]

    result = {
        "fetched": len(published),
        "matched": matched,
        "updated": updated,
        "inserted": inserted,
        "skipped_no_article": skipped,
    }
    logger.info("同步完成: %s", result)
    return result
