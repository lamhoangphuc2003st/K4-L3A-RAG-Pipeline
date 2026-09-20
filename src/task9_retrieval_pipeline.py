"""
Task 9 — Retrieval pipeline hoàn chỉnh.

Luồng xử lý:
    1. Chạy semantic_search và lexical_search.
    2. Fuse hai danh sách bằng RRF đúng một lần.
    3. Lấy best cosine score gốc từ dense results.
    4. Nếu score dưới threshold, thử PageIndex fallback.
    5. Nếu fallback lỗi, trả hybrid results thay vì crash.

Không so sánh threshold với RRF score vì hai thang đo khác nhau: cosine
similarity nằm trong [0, 1] còn RRF score chỉ phản ánh thứ hạng và luôn quanh
1/(k+1) ~ 0.016. Dùng RRF score để quyết fallback sẽ khiến mọi query đều rơi
vào fallback.

``SCORE_THRESHOLD`` phải hiệu chỉnh trên corpus thật bằng query in-domain và
out-of-domain — xem ``calibrate_threshold()`` và mục Fallback trong
``group_project/evaluation/RESULT.md``.
"""

import os

from dotenv import load_dotenv

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search


load_dotenv()


def _configured_threshold(default: float = 0.3) -> float:
    """Đọc SCORE_THRESHOLD từ .env, giữ default nếu trống hoặc sai định dạng."""
    raw = (os.getenv("SCORE_THRESHOLD") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"SCORE_THRESHOLD khong hop le: {raw!r}, dung {default}")
        return default


SCORE_THRESHOLD = _configured_threshold()
DEFAULT_TOP_K = 5

# Lấy dư ứng viên trước khi fuse: RRF chỉ xếp lại thứ hạng, nó không thể kéo
# lên một chunk mà cả hai retriever đều không trả về.
CANDIDATE_MULTIPLIER = 2


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Trả về hybrid hoặc pageindex SearchResult."""
    candidate_k = max(top_k * CANDIDATE_MULTIPLIER, top_k)

    dense = semantic_search(query, top_k=candidate_k)
    sparse = lexical_search(query, top_k=candidate_k)

    # RRF chạy đúng một lần cho mỗi query.
    if use_reranking:
        hybrid = rerank_rrf([dense, sparse], top_k=top_k)
    else:
        hybrid = dense[:top_k]

    # Fallback dựa trên cosine score GỐC của dense, không phải RRF score.
    best_dense_score = dense[0]["score"] if dense else 0.0
    if best_dense_score < score_threshold:
        try:
            fallback = pageindex_search(query, top_k=top_k)
        except Exception as error:
            # PageIndex là dịch vụ ngoài: lỗi của nó không được làm sập UI.
            print(f"PageIndex fallback that bai: {type(error).__name__}: {error}")
        else:
            if fallback:
                return fallback[:top_k]

    return hybrid[:top_k]


def calibrate_threshold(
    in_domain: list[str],
    out_of_domain: list[str],
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    """In best dense score của hai nhóm query và gợi ý ngưỡng ở giữa.

    Ngưỡng tốt nằm giữa ``min(in_domain)`` và ``max(out_of_domain)``. Nếu hai
    cụm chồng lên nhau thì không có ngưỡng nào tách sạch được — lúc đó phải sửa
    corpus hoặc chunking chứ không phải chỉnh số.
    """

    def best_score(query: str) -> float:
        results = semantic_search(query, top_k=top_k)
        return results[0]["score"] if results else 0.0

    in_scores = {query: best_score(query) for query in in_domain}
    out_scores = {query: best_score(query) for query in out_of_domain}

    print("In-domain (nen retrieve duoc):")
    for query, score in sorted(in_scores.items(), key=lambda item: item[1]):
        print(f"  {score:.4f}  {query}")
    print("Out-of-domain (nen fallback / tu choi):")
    for query, score in sorted(out_scores.items(), key=lambda item: item[1], reverse=True):
        print(f"  {score:.4f}  {query}")

    lowest_in = min(in_scores.values(), default=0.0)
    highest_out = max(out_scores.values(), default=0.0)
    separated = lowest_in > highest_out
    suggested = round((lowest_in + highest_out) / 2, 3)

    print(f"\nThap nhat in-domain : {lowest_in:.4f}")
    print(f"Cao nhat out-domain : {highest_out:.4f}")
    if separated:
        print(f"Hai cum tach roi -> SCORE_THRESHOLD={suggested}")
    else:
        print(
            "Hai cum CHONG NHAU -> khong co nguong nao tach sach. "
            "Xem lai chunk size hoac bo sung tai lieu."
        )

    return {
        "in_domain": in_scores,
        "out_of_domain": out_scores,
        "lowest_in_domain": lowest_in,
        "highest_out_of_domain": highest_out,
        "separated": separated,
        "suggested_threshold": suggested,
    }


if __name__ == "__main__":
    for result in retrieve("test query", top_k=3):
        print(
            f"[{result['retrieval_method']}] {result['score']:.4f} "
            f"{result['metadata']['title']} — {result['content'][:80]}..."
        )
