"""全流程端到端测试 — 采集→选题→生成→审核→封面→多渠道草稿保存"""
import asyncio
import logging
import os

# 设置测试环境变量
os.environ["PUBLISH_TARGETS"] = "toutiao,baijiahao"

from app.modules.entertainment.module import EntertainmentModule

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 80)
    logger.info("开始全流程端到端测试")
    logger.info("=" * 80)

    logger.info("\n配置信息:")
    logger.info(f"  活动模块: EntertainmentModule")
    logger.info(f"  发布目标: toutiao, baijiahao")
    logger.info(f"  发布模式: 草稿 (as_draft=True)")

    module = EntertainmentModule()

    logger.info("\n" + "=" * 80)
    logger.info("阶段 1/6: 采集新闻池")
    logger.info("=" * 80)
    news_pool = await module.collect_topics()
    logger.info(f"✅ 采集完成: {len(news_pool)} 条新闻")
    if news_pool:
        for i, news in enumerate(news_pool[:5], 1):
            logger.info(f"  {i}. {news.title[:60]} (来源: {news.source})")

    if not news_pool:
        logger.error("❌ 新闻池为空,测试终止")
        return

    logger.info("\n" + "=" * 80)
    logger.info("阶段 2/6: 自动选题")
    logger.info("=" * 80)
    selected = await module.select_topics(news_pool, count=1)
    logger.info(f"✅ 选题完成: {len(selected)} 个话题")
    if selected:
        logger.info(f"  选中话题: {selected[0].title}")
        logger.info(f"  来源: {selected[0].source}")
        logger.info(f"  描述: {selected[0].description[:100] if selected[0].description else '无'}")

    if not selected:
        logger.error("❌ 未选出话题,测试终止")
        return

    logger.info("\n" + "=" * 80)
    logger.info("阶段 3/6: 生成文章")
    logger.info("=" * 80)
    topic = selected[0]
    article = await module.generate_article(topic)
    logger.info(f"✅ 文章生成完成")
    logger.info(f"  标题: {article['title']}")
    logger.info(f"  摘要: {article['digest'][:100]}")
    logger.info(f"  质量评分: {article['style_score']}/100")
    logger.info(f"  内容长度: {len(article['content_markdown'])} 字符")

    logger.info("\n" + "=" * 80)
    logger.info("阶段 4/6: 内容审核")
    logger.info("=" * 80)
    review = await module.guard.review(article)
    logger.info(f"✅ 审核完成")
    logger.info(f"  风险等级: {review['risk_level']}")
    if review.get('issues'):
        logger.info(f"  发现问题: {len(review['issues'])} 项")
        for issue in review['issues'][:3]:
            logger.info(f"    - {issue}")

    if review['risk_level'] == 'high':
        logger.error("❌ 内容风险过高,测试终止")
        return

    logger.info("\n" + "=" * 80)
    logger.info("阶段 5/6: 生成封面")
    logger.info("=" * 80)
    from app.services.wechat.cover_generator import generate_cover_async
    cover_path = await generate_cover_async(article['title'], content=article['content_html'])
    logger.info(f"✅ 封面生成完成")
    logger.info(f"  封面路径: {cover_path}")

    logger.info("\n" + "=" * 80)
    logger.info("阶段 6/6: 多渠道发布(草稿)")
    logger.info("=" * 80)

    from app.services.publish import ArticleProduct
    product = ArticleProduct(
        title=article['title'],
        digest=article['digest'],
        content_html=article['content_html'],
        content_md=article['content_markdown'],
        author=module.author,
        cover_path=cover_path,
        quality_score=article['style_score'],
        ai_disclosure=True,
    )

    results = await module.router.publish(product, targets=module._publish_targets, as_draft=True)

    logger.info(f"✅ 发布完成: {len(results)} 个渠道")
    all_ok = True
    for ch_name, r in results.items():
        status_icon = "✅" if r.ok else "❌"
        logger.info(f"  {status_icon} {ch_name}: status={r.status}")
        if r.ok:
            logger.info(f"      draft_id={r.draft_id}")
            if r.url:
                logger.info(f"      url={r.url}")
        else:
            logger.info(f"      error={r.error}")
            all_ok = False

    logger.info("\n" + "=" * 80)
    if all_ok:
        logger.info("🎉 全流程测试完成 - 所有渠道成功")
    else:
        logger.warning("⚠️  全流程测试完成 - 部分渠道失败")
    logger.info("=" * 80)

    logger.info("\n测试摘要:")
    logger.info(f"  话题: {topic.title}")
    logger.info(f"  标题: {article['title']}")
    logger.info(f"  质量: {article['style_score']}/100")
    logger.info(f"  风险: {review['risk_level']}")
    logger.info(f"  渠道: {', '.join(results.keys())}")
    logger.info(f"  结果: {'全部成功' if all_ok else '部分失败'}")


if __name__ == "__main__":
    asyncio.run(main())
