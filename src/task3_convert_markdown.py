"""
Task 3 — Chuẩn hóa dữ liệu sang Markdown.

PDF/DOCX trong ``data/landing/legal`` được convert bằng MarkItDown; JSON trong
``data/landing/news`` được ghép metadata header vào đầu file Markdown. Kết quả
giữ đúng cấu trúc ``standardized/legal`` và ``standardized/news``.

File ngắn hơn ``MIN_CONTENT_LENGTH`` (thường là PDF scan ảnh, không có text
layer) bị loại và xoá bản cũ để không lọt vào bước index. Chạy lại script ghi
đè đúng tên file cũ nên không tạo file trùng.
"""

import json
import re
from pathlib import Path


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"

# Ngưỡng của tests/test_acceptance.py: mỗi file .md >= 200 ky tu sau strip.
MIN_CONTENT_LENGTH = 200

MIN_LEGAL_FILES = 3
MIN_NEWS_FILES = 5

DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx"}


def normalize_markdown(text: str) -> str:
    """Bỏ khoảng trắng cuối dòng và nén dòng trống lặp."""
    text = re.sub(r"[ \t]+\n", "\n", text.replace("\r\n", "\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def write_if_long_enough(path: Path, content: str) -> bool:
    """Ghi file khi đủ dài; nếu không thì xoá bản cũ và trả về False."""
    if len(content.strip()) < MIN_CONTENT_LENGTH:
        path.unlink(missing_ok=True)
        return False
    path.write_text(content, encoding="utf-8")
    return True


def convert_legal_docs() -> None:
    """Convert PDF/DOCX vào ``standardized/legal``."""
    from markitdown import MarkItDown

    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    converter = MarkItDown()
    converted = 0
    for path in sorted(legal_dir.iterdir()):
        if path.suffix.lower() not in DOCUMENT_SUFFIXES:
            continue

        try:
            result = converter.convert(str(path))
        except Exception as error:
            print(f"  Failed: {path.name} — {type(error).__name__}: {error}")
            continue

        title = path.stem.replace("-", " ").replace("_", " ").strip()
        body = normalize_markdown(result.text_content or "")
        document = f"# {title}\n\n**Source:** {path.name}\n\n---\n\n{body}\n"

        target = output_dir / f"{path.stem}.md"
        if write_if_long_enough(target, document):
            converted += 1
            print(f"  Saved: legal/{target.name} ({len(body)} chars)")
        else:
            print(f"  Skipped (khong co text layer, can OCR): {path.name}")

    print(f"Legal Markdown: {converted}/{MIN_LEGAL_FILES} required")
    if converted < MIN_LEGAL_FILES:
        raise RuntimeError(
            f"Chi chuan hoa duoc {converted} tai lieu legal, can toi thieu "
            f"{MIN_LEGAL_FILES}. Bo sung PDF co text layer vao Task 1."
        )


def convert_news_articles() -> None:
    """Convert JSON vào ``standardized/news``."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    for path in sorted(news_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            print(f"  Failed: {path.name} — {error}")
            continue

        header = (
            f"# {data['title']}\n\n"
            f"**Source:** {data['url']}\n\n"
            f"**Crawled:** {data['date_crawled']}\n\n---\n\n"
        )
        body = normalize_markdown(data.get("content_markdown") or "")

        target = output_dir / f"{path.stem}.md"
        if write_if_long_enough(target, header + body + "\n"):
            converted += 1
            print(f"  Saved: news/{target.name} ({len(body)} chars)")
        else:
            print(f"  Skipped (noi dung qua ngan): {path.name}")

    print(f"News Markdown: {converted}/{MIN_NEWS_FILES} required")
    if converted < MIN_NEWS_FILES:
        raise RuntimeError(
            f"Chi chuan hoa duoc {converted} bai news, can toi thieu "
            f"{MIN_NEWS_FILES}. Chay lai Task 2 hoac bo sung URL."
        )


def convert_all() -> None:
    """Convert toàn bộ dữ liệu landing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Converting legal documents...")
    convert_legal_docs()
    print("Converting news articles...")
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
