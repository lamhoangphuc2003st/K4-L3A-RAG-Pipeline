"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.

Corpus được nạp lazy bằng ``load_chunks()`` của Task 4 — đúng bộ chunks đã
index vào ChromaDB — để ID của BM25 và của dense trùng nhau, nếu không RRF
(Task 7) sẽ fuse nhầm.
"""

import re


CORPUS: list[dict] = []

# Token thường: \w+ theo Unicode nên giữ nguyên dấu tiếng Việt ("miễn", "giảm").
_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
# Mã văn bản / số hiệu ("70/2025/nđ-cp", "1234/qđ-bgdđt"): giữ nguyên cả cụm để
# query tra cứu đúng số hiệu ăn điểm cao hơn hẳn các chunk chỉ trùng chữ rời.
_CODE_PATTERN = re.compile(r"\w*\d[\w]*(?:[/-]\w+)+", re.UNICODE)

# Cache index theo đúng object corpus đang dùng; monkeypatch/đổi corpus sẽ tự
# build lại thay vì ăn cache cũ.
_bm25_cache: tuple[int, int, object, list[set[str]]] | None = None


def _tokenize(text: str) -> list[str]:
    """Tách token cho tiếng Việt: lowercase, bỏ dấu câu, giữ dấu thanh.

    Không tách từ ghép (word segmentation) vì BM25 ở đây chỉ cần khớp từ khóa;
    dense search lo phần ngữ nghĩa.
    """
    lowered = text.lower()
    tokens = _WORD_PATTERN.findall(lowered)
    tokens.extend(_CODE_PATTERN.findall(lowered))
    return tokens


def _corpus() -> list[dict]:
    """Trả về corpus đang dùng, nạp từ Task 4 nếu ``CORPUS`` còn rỗng."""
    global CORPUS

    if not CORPUS:
        from .task4_chunking_indexing import load_chunks

        CORPUS = load_chunks()
    return CORPUS


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    from rank_bm25 import BM25Okapi

    if not corpus:
        raise ValueError("Corpus rong — chay `python -m src.task4_chunking_indexing` truoc.")
    return BM25Okapi([_tokenize(item["content"]) for item in corpus])


def _get_index(corpus: list[dict]) -> tuple[object, list[set[str]]]:
    """Trả về (bm25 index, token set từng chunk) và cache theo corpus hiện tại."""
    global _bm25_cache

    key = (id(corpus), len(corpus))
    if _bm25_cache is not None and _bm25_cache[:2] == key:
        return _bm25_cache[2], _bm25_cache[3]

    index = build_bm25_index(corpus)
    token_sets = [set(_tokenize(item["content"])) for item in corpus]
    _bm25_cache = (key[0], key[1], index, token_sets)
    return index, token_sets


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    corpus = _corpus()
    query_tokens = _tokenize(query or "")
    if not corpus or not query_tokens or top_k <= 0:
        return []

    index, token_sets = _get_index(corpus)
    scores = index.get_scores(query_tokens)
    query_set = set(query_tokens)

    # Chỉ giữ chunk thực sự chứa ít nhất một token của query. Không lọc bằng
    # `score > 0`: BM25Okapi cho idf = log(N-df+0.5) - log(df+0.5), với corpus
    # nhỏ (N=2, df=1) idf bằng đúng 0 nên chunk khớp hoàn toàn vẫn được 0 điểm
    # và sẽ bị loại oan. Lọc theo token overlap đúng ý đồ hơn và không phụ
    # thuộc kích thước corpus; score âm (idf bị floor) vẫn bị bỏ.
    scored = [
        (float(score), index_)
        for index_, score in enumerate(scores)
        if float(score) >= 0 and query_set & token_sets[index_]
    ]
    # Tie-break bằng ID để kết quả tái lập được giữa các lần chạy.
    scored.sort(key=lambda pair: (-pair[0], corpus[pair[1]]["id"]))

    results: list[dict] = []
    seen: set[str] = set()
    for score, index in scored:
        item = corpus[index]
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": score,
                "metadata": dict(item["metadata"]),
                "retrieval_method": "bm25",
            }
        )
        if len(results) == top_k:
            break
    return results


if __name__ == "__main__":
    for result in lexical_search("mức học bổng khuyến khích học tập", top_k=3):
        print(f"{result['score']:.4f}  {result['id']}")
        print(f"        {result['content'][:120].replace(chr(10), ' ')}")
