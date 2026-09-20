"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.
"""

from .task4_chunking_indexing import embed_texts, get_collection


def _first(response: dict, key: str, size: int) -> list:
    """Lấy hàng đầu tiên của Chroma response, bù ``None`` nếu key vắng mặt."""
    rows = response.get(key)
    if not rows:
        return [None] * size
    row = rows[0]
    return list(row) if row is not None else [None] * size


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về dense SearchResult theo score giảm dần.

    Dùng đúng ``embed_texts`` của Task 4 để query vector và document vector
    nằm cùng không gian embedding.
    """
    if not query or not query.strip() or top_k <= 0:
        return []

    query_vector = embed_texts([query])[0]
    response = get_collection().query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    ids = _first(response, "ids", 0)
    size = len(ids)
    documents = _first(response, "documents", size)
    metadatas = _first(response, "metadatas", size)
    distances = _first(response, "distances", size)

    results: list[dict] = []
    seen: set[str] = set()
    for item_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
        if not item_id or item_id in seen or not content:
            continue
        seen.add(item_id)
        results.append(
            {
                "id": item_id,
                "content": content,
                # Chroma trả cosine *distance*; Task 9 so threshold với đúng con
                # số similarity này nên không normalize thêm lần nữa.
                "score": max(0.0, 1.0 - float(distance)),
                "metadata": dict(metadata or {}),
                "retrieval_method": "dense",
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    for result in semantic_search("Mức thu học phí được quy định thế nào?", top_k=3):
        print(f"{result['score']:.4f}  {result['id']}")
        print(f"        {result['content'][:120].replace(chr(10), ' ')}")
