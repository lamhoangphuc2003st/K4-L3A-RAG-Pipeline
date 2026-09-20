"""
Task 2 — Crawl bài viết/thông báo về dịch vụ đại học.

Chủ đề: học phí, học bổng, ký túc xá, thư viện, đăng ký học phần.

Mỗi URL được crawl bằng Crawl4AI (Playwright/Chromium). Nếu browser chưa cài
hoặc site chặn headless browser, script tự chuyển sang fallback
``requests`` + ``MarkItDown`` để vẫn lấy được Markdown. Mỗi bài lưu thành một
JSON đủ 4 key ``url``, ``title``, ``date_crawled``, ``content_markdown``.

Cài browser trước khi chạy:
    python -m playwright install chromium
"""

import asyncio
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

import requests


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

# Số bài tối thiểu theo yêu cầu của đề (tests/test_acceptance.py).
MIN_ARTICLES = 5

# Bài quá ngắn thường là trang chặn hoặc redirect; bước Task 3 cần >=200 ký tự.
MIN_CONTENT_LENGTH = 200

REQUEST_TIMEOUT = 45
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

ARTICLE_URLS = [
    # Học phí
    "https://tuoitre.vn/hoc-phi-dai-hoc-2026-tiep-tuc-tang-co-nganh-vot-gan-50-20260316063050911.htm",
    "https://giaoducthudo.giaoducthoidai.vn/hoc-phi-tang-ho-tro-sinh-vien-duoc-mo-rong-217966.html",
    "https://baolamdong.vn/chi-tiet-hoc-phi-2026-cua-vinuni-438111.html",
    # Học bổng
    "https://giaoducthoidai.vn/nhieu-hoc-bong-va-mien-giam-hoc-phi-tai-truong-dai-hoc-kien-giang-nam-2026-post784848.html",
    "https://htv.vn/nhieu-truong-dai-hoc-tang-hoc-bong-mien-giam-hoc-phi-cho-tan-sinh-vien-nam-2026-222260313110558601.htm",
    # Ký túc xá
    "https://ktxhcm.edu.vn/sinh-vien-noi-tru/thong-bao-menu/ve-viec-dang-ky-o-ky-tuc-xa-nam-hoc-2026-2027",
    "https://www.ktxhcm.edu.vn/tieu-diem-noi-bat/n-i-quy-cong-tac-sinh-vien-n-i-tru-t-i-ky-tuc-xa-d-i-h-c-qu-c-gia-tp-hcm",
    "https://sict.haui.edu.vn/vn/thong-bao/huong-dan-dang-ky-phong-o-ky-tuc-xa-truc-tuyen-cho-tan-sinh-vien-nam-hoc-2026-2027/71858",
    "https://tuyensinh.ufm.edu.vn/vi/thong-tin-tuyen-sinh-dai-hoc-chinh-quy/thong-bao-dang-ky-o-ky-tuc-xa-danh-cho-tan-sinh-vien-2026",
]


def _clean_markdown(text: str) -> str:
    """Bỏ dòng trống lặp và khoảng trắng cuối dòng."""
    text = re.sub(r"[ \t]+\n", "\n", text.replace("\r\n", "\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _title_from_html(html: str, fallback: str) -> str:
    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r"<title[^>]*>(.*?)</title>",
        r"<h1[^>]*>(.*?)</h1>",
    ):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            title = re.sub(r"<[^>]+>", "", match.group(1))
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                return title
    return fallback


def fetch_with_markitdown(url: str) -> dict:
    """Fallback: tải HTML bằng requests rồi convert sang Markdown."""
    from markitdown import MarkItDown

    response = requests.get(
        url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    html = response.text

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "page.html"
        tmp_path.write_text(html, encoding="utf-8")
        converted = MarkItDown().convert(str(tmp_path))

    return {
        "url": url,
        "title": _title_from_html(html, fallback=url),
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": _clean_markdown(converted.text_content or ""),
    }


async def crawl_article(url: str, crawler: object | None = None) -> dict:
    """Crawl một URL và trả về dict đúng 4 key mà acceptance test yêu cầu.

    ``crawler`` cho phép ``crawl_all`` mở Chromium một lần rồi dùng lại cho mọi
    URL. Khi Crawl4AI không dùng được, hàm rơi về ``fetch_with_markitdown``.
    """
    try:
        from crawl4ai import AsyncWebCrawler

        if crawler is None:
            async with AsyncWebCrawler(verbose=False) as own_crawler:
                return await crawl_article(url, own_crawler)

        result = await crawler.arun(url=url)
        if not getattr(result, "success", True):
            raise RuntimeError(getattr(result, "error_message", "crawl failed"))

        # Crawl4AI 0.9 trả về object MarkdownGenerationResult, không phải str.
        markdown = getattr(result, "markdown", "") or ""
        markdown = getattr(markdown, "raw_markdown", None) or str(markdown)
        markdown = _clean_markdown(markdown)

        metadata = getattr(result, "metadata", None) or {}
        title = (metadata.get("title") or "").strip()
        if not title:
            title = _title_from_html(getattr(result, "html", "") or "", fallback=url)

        if len(markdown) < MIN_CONTENT_LENGTH:
            raise RuntimeError(f"markdown too short ({len(markdown)} chars)")

        return {
            "url": url,
            "title": title,
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": markdown,
        }
    except Exception as error:
        print(f"  Crawl4AI khong dung duoc ({type(error).__name__}: {error}) -> fallback")
        return fetch_with_markitdown(url)


def validate_article(article: dict) -> None:
    """Raise khi bài crawl thiếu key hoặc nội dung quá ngắn."""
    for key in ("url", "title", "date_crawled", "content_markdown"):
        if not str(article.get(key, "")).strip():
            raise ValueError(f"missing or empty field: {key}")
    if len(article["content_markdown"].strip()) < MIN_CONTENT_LENGTH:
        raise ValueError(
            f"content_markdown chi co {len(article['content_markdown'].strip())} ky tu"
        )


async def crawl_all() -> None:
    """Crawl và lưu từng bài thành một file JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    crawler = None
    context = None
    try:
        from crawl4ai import AsyncWebCrawler

        context = AsyncWebCrawler(verbose=False)
        crawler = await context.__aenter__()
    except Exception as error:
        print(f"Khong mo duoc Chromium ({error}) -> dung fallback cho toan bo URL")

    saved = 0
    try:
        for index, url in enumerate(ARTICLE_URLS, 1):
            print(f"[{index}/{len(ARTICLE_URLS)}] {url}")
            try:
                article = await crawl_article(url, crawler)
                validate_article(article)
                output = DATA_DIR / f"article_{index:02d}.json"
                output.write_text(
                    json.dumps(article, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                saved += 1
                print(f"  Saved: {output.name} ({len(article['content_markdown'])} chars)")
            except Exception as error:
                print(f"  Failed: {url} — {error}")
    finally:
        if context is not None:
            await context.__aexit__(None, None, None)

    print(f"Saved {saved} articles, {MIN_ARTICLES} required")
    if saved < MIN_ARTICLES:
        raise RuntimeError(
            f"Chi crawl duoc {saved} bai, can toi thieu {MIN_ARTICLES}. "
            "Bo sung URL cong khai khac vao ARTICLE_URLS."
        )


if __name__ == "__main__":
    asyncio.run(crawl_all())
