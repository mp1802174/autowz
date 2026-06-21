from app.services.publish.channels.baijiahao import BaijiahaoChannel
from app.services.publish.channels.toutiao import ToutiaoChannel
from app.services.publish.product import ArticleProduct


def test_non_wechat_channels_strip_guide_and_insert_cover_image():
    product = ArticleProduct(
        title="测试",
        digest="",
        content_html=(
            '<p><img src="old.jpg" /></p>'
            "<p>正文</p>"
            '<section><p>—— 精彩文章导读 ——</p><a href="#">旧导读</a></section>'
        ),
    )

    for channel in (ToutiaoChannel, BaijiahaoChannel):
        html = channel._to_html(product, image_url="https://example.com/new.jpg")
        assert "精彩文章导读" not in html
        assert "old.jpg" not in html
        assert html.startswith('<p><img src="https://example.com/new.jpg" /></p>')


def test_toutiao_uses_real_draft_save_mode():
    # 头条接口里 save=1 是发表，save=0 才是保存草稿。
    assert ToutiaoChannel.DRAFT_SAVE_MODE == "0"
