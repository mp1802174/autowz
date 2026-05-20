import re


def extract_cover_url(content_html: str) -> str:
    """从文章 HTML 中提取第一个 <img> 的 src 作为封面图 URL。"""
    if not content_html:
        return ""
    match = re.search(r'<img[^>]*?(?<![a-zA-Z\-])src=["\']([^"\']+)["\']', content_html, re.IGNORECASE)
    if match:
        url = match.group(1)
        if not url.startswith("file://"):
            return url
    return ""


def build_reading_guide_html(articles: list[dict]) -> str:
    """
    生成「精彩文章导读」底部区块 HTML。

    articles 每项包含: title, article_url, content_html
    """
    if not articles:
        return ""

    items_html = ""
    for art in articles:
        cover_url = extract_cover_url(art.get("content_html", ""))
        title = art.get("title", "")
        url = art.get("article_url", "")

        img_tag = (
            f'<img src="{cover_url}" '
            f'style="width:100%; display:block; border-radius:4px; margin-bottom:6px;" />'
            if cover_url
            else ""
        )

        items_html += (
            f'<a href="{url}" style="display:block; text-decoration:none; margin-bottom:20px;">'
            f"{img_tag}"
            f'<p style="font-size:14px; color:#333; margin:0; line-height:1.6;">{title}</p>'
            f"</a>"
        )

    return (
        '<section style="margin:48px 0 0 0; padding:0;">'
        '<p style="text-align:center; font-size:15px; color:#555; '
        'letter-spacing:3px; margin:0 0 20px 0;">—— 精彩文章导读 ——</p>'
        f"{items_html}"
        "</section>"
    )
