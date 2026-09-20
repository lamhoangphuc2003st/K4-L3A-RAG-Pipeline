"""
Task 7 — Reciprocal Rank Fusion.

RRF gộp nhiều bảng xếp hạng mà không cộng trực tiếp cosine score với BM25
score. Công thức: RRF(d) = sum(1 / (k + rank)), rank bắt đầu từ 1.

Lưu ý: RRF score chỉ phản ánh thứ hạng, không dùng để quyết định fallback.

-> Dùng Jina hoặc self host hoặc bất cứ công cụ nào bạn quen
"""


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Fuse nhiều ranked lists và trả hybrid SearchResult.

    Dense score (cosine, 0..1) và BM25 score (không chặn trên) không cùng
    thang đo nên không cộng trực tiếp được. RRF chỉ đọc *thứ hạng* của từng
    item trong mỗi list, vì vậy hai nguồn khác thang đo vẫn gộp được.

    Một document xuất hiện ở nhiều list sẽ cộng dồn điểm từng list -> đồng
    thuận giữa dense và BM25 được thưởng. ``k`` làm giảm khoảng cách giữa các
    rank đầu bảng, ``k=60`` là giá trị mặc định trong bài báo gốc.
    """
    if top_k <= 0:
        return []

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        if not ranked_list:
            continue
        seen_in_list: set[str] = set()
        for rank, item in enumerate(ranked_list, start=1):
            item_id = item["id"]
            if item_id in seen_in_list:
                # Một list trả trùng ID là lỗi của retriever; chỉ tính rank tốt
                # nhất để không thổi điểm document đó lên.
                continue
            seen_in_list.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            items.setdefault(item_id, item)

    # Tie-break bằng ID để thứ tự ổn định giữa các lần chạy (evaluation A/B cần
    # kết quả tái lập được).
    ranked_ids = sorted(scores, key=lambda item_id: (-scores[item_id], item_id))

    results: list[dict] = []
    for item_id in ranked_ids[:top_k]:
        result = dict(items[item_id])
        result["metadata"] = dict(items[item_id]["metadata"])
        result["score"] = scores[item_id]
        result["retrieval_method"] = "hybrid"
        results.append(result)
    return results


if __name__ == "__main__":
    dense = [
        {"id": "a", "content": "hoc phi", "score": 0.81,
         "metadata": {"source": "hocphi.md", "title": "Hoc phi", "doc_type": "legal",
                      "url": "", "chunk_index": 0},
         "retrieval_method": "dense"},
        {"id": "b", "content": "hoc bong", "score": 0.74,
         "metadata": {"source": "hocbong.md", "title": "Hoc bong", "doc_type": "legal",
                      "url": "", "chunk_index": 1},
         "retrieval_method": "dense"},
    ]
    bm25 = [
        {"id": "b", "content": "hoc bong", "score": 7.2,
         "metadata": {"source": "hocbong.md", "title": "Hoc bong", "doc_type": "legal",
                      "url": "", "chunk_index": 1},
         "retrieval_method": "bm25"},
        {"id": "c", "content": "ky tuc xa", "score": 5.5,
         "metadata": {"source": "ktx.md", "title": "KTX", "doc_type": "legal",
                      "url": "", "chunk_index": 2},
         "retrieval_method": "bm25"},
    ]
    for result in rerank_rrf([dense, bm25], top_k=3, k=60):
        print(f"{result['id']:<4} {result['score']:.6f} {result['retrieval_method']}")
