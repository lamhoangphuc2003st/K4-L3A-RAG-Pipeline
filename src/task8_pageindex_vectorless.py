"""
Task 8 — PageIndex vectorless fallback.

Hướng dẫn:
    1. Đọc PAGEINDEX_API_KEY từ .env.
    2. Upload tài liệu ở định dạng PageIndex hỗ trợ.
    3. Cache document IDs để không upload lại.
    4. Parse kết quả thành SearchResult có method pageindex.

PageIndex là dịch vụ ngoài nên module này được viết theo nguyên tắc: mọi lỗi
(thiếu key, SDK chưa cài, timeout, response đổi schema) đều trả danh sách rỗng
thay vì ném exception lên Task 9. Task 9 vẫn có ``try/except`` bọc ngoài, nhưng
không nên dựa vào đó để xử lý trường hợp bình thường là "nhóm không có key".

Response của SDK được parse bằng ``_normalise_node()`` — dò nhiều tên field khả
dĩ thay vì hard-code một tên duy nhất. Khi nhóm có API key thật, chạy
``python -m src.task8_pageindex_vectorless --probe`` để in raw response và chốt
lại đúng tên field.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

# Cache đã nằm trong .gitignore.
DOC_ID_CACHE = Path(__file__).parent.parent / "pageindex_doc_ids.json"
PDF_CACHE_DIR = Path(__file__).parent.parent / "pageindex_pdfs"

REQUEST_TIMEOUT = 30


def is_enabled() -> bool:
    """PageIndex chỉ hoạt động khi có API key."""
    return bool(PAGEINDEX_API_KEY.strip())


def _load_cache() -> dict:
    if not DOC_ID_CACHE.exists():
        return {}
    try:
        return json.loads(DOC_ID_CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict) -> None:
    DOC_ID_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _get_client():
    """Tạo PageIndex client; trả None nếu thiếu key hoặc chưa cài SDK."""
    if not is_enabled():
        return None
    try:
        from pageindex import PageIndexClient
    except ImportError:
        print("SDK pageindex chua duoc cai — bo qua fallback.")
        return None
    try:
        return PageIndexClient(api_key=PAGEINDEX_API_KEY)
    except Exception as error:
        print(f"Khong khoi tao duoc PageIndex client: {type(error).__name__}: {error}")
        return None


def _markdown_to_pdf(source: Path, target: Path) -> Path | None:
    """PageIndex nhận PDF; convert Markdown sang PDF tạm bằng fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        print("fpdf2 chua duoc cai — khong convert duoc Markdown sang PDF.")
        return None

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", size=10)
        text = source.read_text(encoding="utf-8")
        # FPDF core font là latin-1; giữ nội dung chạy được thay vì crash.
        safe = text.encode("latin-1", errors="replace").decode("latin-1")
        for line in safe.splitlines():
            pdf.multi_cell(0, 5, line or " ")
        target.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(target))
        return target
    except Exception as error:
        print(f"Convert PDF that bai cho {source.name}: {type(error).__name__}: {error}")
        return None


def upload_documents() -> dict:
    """Upload tài liệu và lưu mapping source -> document ID."""
    client = _get_client()
    if client is None:
        print("PageIndex chua san sang — khong upload gi.")
        return {}

    cache = _load_cache()
    markdown_files = sorted(STANDARDIZED_DIR.rglob("*.md"))
    if not markdown_files:
        print(f"Khong tim thay Markdown trong {STANDARDIZED_DIR} — chay Task 3 truoc.")
        return cache

    for path in markdown_files:
        key = path.relative_to(STANDARDIZED_DIR).as_posix()
        if key in cache:
            continue  # đã upload ở lần chạy trước

        pdf_path = _markdown_to_pdf(path, PDF_CACHE_DIR / f"{path.stem}.pdf")
        if pdf_path is None:
            continue

        try:
            response = client.submit_document(str(pdf_path))
        except Exception as error:
            print(f"Upload that bai {key}: {type(error).__name__}: {error}")
            continue

        doc_id = _extract_first(
            response, ("doc_id", "document_id", "id", "documentId")
        )
        if not doc_id:
            print(f"Khong doc duoc document id tu response cua {key}: {response!r}")
            continue

        cache[key] = doc_id
        print(f"Uploaded: {key} -> {doc_id}")

    _save_cache(cache)
    print(f"Cache: {len(cache)} document ({DOC_ID_CACHE.name})")
    return cache


def _extract_first(payload: object, keys: tuple[str, ...]) -> str | None:
    """Lấy giá trị đầu tiên khớp một trong các tên field."""
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "__dict__") and not isinstance(payload, dict):
        payload = vars(payload)
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalise_node(node: object, doc_key: str, rank: int, top_k: int) -> dict | None:
    """Đổi một retrieved node của PageIndex thành SearchResult."""
    if hasattr(node, "__dict__") and not isinstance(node, dict):
        node = vars(node)
    if not isinstance(node, dict):
        return None

    content = _extract_first(node, ("text", "content", "node_text", "chunk", "summary"))
    if not content:
        return None

    node_id = _extract_first(node, ("node_id", "id", "chunk_id")) or f"node-{rank}"

    raw_score = node.get("score", node.get("relevance_score"))
    if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
        score = float(raw_score)
    else:
        # API không trả score -> gán giảm dần theo rank để giữ thứ tự hợp lệ.
        score = (top_k - rank + 1) / top_k

    return {
        "id": f"pageindex::{doc_key}::{node_id}",
        "content": content,
        "score": score,
        "metadata": {
            "source": doc_key,
            "title": Path(doc_key).stem.replace("-", " "),
            "doc_type": "legal" if "legal" in doc_key else "news",
            "url": None,
            "chunk_index": rank - 1,
        },
        "retrieval_method": "pageindex",
    }


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Trả về pageindex SearchResult; danh sách rỗng khi dịch vụ không khả dụng."""
    client = _get_client()
    if client is None:
        return []

    cache = _load_cache()
    if not cache:
        cache = upload_documents()
    if not cache:
        return []

    results: list[dict] = []
    for doc_key, doc_id in cache.items():
        try:
            response = client.retrieve(doc_id, query)
        except Exception as error:
            print(f"PageIndex retrieve loi ({doc_key}): {type(error).__name__}: {error}")
            continue

        nodes = response
        if isinstance(response, dict):
            for field in ("retrieved_nodes", "nodes", "results", "data"):
                if isinstance(response.get(field), list):
                    nodes = response[field]
                    break
        if not isinstance(nodes, list):
            continue

        for rank, node in enumerate(nodes[:top_k], 1):
            item = _normalise_node(node, doc_key, rank, top_k)
            if item is not None:
                results.append(item)

    # Gộp nhiều document -> khử trùng ID rồi cắt top_k.
    unique: dict[str, dict] = {}
    for item in results:
        if item["id"] not in unique:
            unique[item["id"]] = item

    ranked = sorted(unique.values(), key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]


if __name__ == "__main__":
    import sys

    if "--probe" in sys.argv:
        # In raw response de chot dung ten field cua SDK.
        client = _get_client()
        if client is None:
            print("Chua co PAGEINDEX_API_KEY.")
        else:
            cache = _load_cache() or upload_documents()
            for doc_key, doc_id in list(cache.items())[:1]:
                print(f"--- raw retrieve response cho {doc_key} ---")
                print(client.retrieve(doc_id, "hoc phi"))
    else:
        upload_documents()
        for item in pageindex_search("hoc phi", top_k=3):
            print(f"{item['score']:.3f}  {item['id']}  {item['content'][:80]}...")
