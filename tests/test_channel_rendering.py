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

    toutiao_html = ToutiaoChannel._to_html(product, image_url="https://example.com/new.jpg")
    assert "精彩文章导读" not in toutiao_html
    assert "old.jpg" not in toutiao_html
    assert toutiao_html.startswith('<p><img src="https://example.com/new.jpg" /></p>')

    baijiahao_html = BaijiahaoChannel._to_html(product, image_url="https://example.com/new.jpg")
    assert "精彩文章导读" not in baijiahao_html
    assert "old.jpg" not in baijiahao_html
    assert 'src="https://example.com/new.jpg"' in baijiahao_html
    assert 'data-bjh-type="IMG"' in baijiahao_html


def test_toutiao_uses_real_draft_save_mode():
    # 头条自动化存草稿会触发 7050，当前按用户授权直接发布。
    assert ToutiaoChannel.PUBLISH_SAVE_MODE == "1"
