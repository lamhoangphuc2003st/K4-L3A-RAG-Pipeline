"""
Task 4 — Chunking, embedding và indexing.

Đường đi: đọc Markdown trong ``data/standardized`` -> chunk bằng
``RecursiveCharacterTextSplitter`` -> embed bằng đúng một provider -> upsert vào
ChromaDB persistent với cosine distance.

ID chunk ổn định theo dạng ``legal/hocphi.md::chunk-3`` nên chạy lại pipeline
chỉ ghi đè, không nhân đôi dữ liệu.

Task 5 (dense search) và Task 6 (BM25) phải dùng chung ``embed_texts()`` và
``load_chunks()`` của module này để dense và lexical chạy trên cùng corpus, nếu
không RRF sẽ fuse sai ID.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Giải thích lựa chọn tham số trong báo cáo nhóm.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

COLLECTION_NAME = "rag_documents"

# Batch nhỏ cho model local (RAM), lớn hơn cho API.
LOCAL_BATCH_SIZE = 16
API_BATCH_SIZE = 64
UPSERT_BATCH_SIZE = 500

# Cache model local để mọi lần gọi embed_texts() dùng lại một instance.
_sentence_transformer = None


def _provider() -> str:
    return (os.getenv("EMBEDDING_PROVIDER") or "sentence_transformers").strip().lower()


def _model_name() -> str:
    return (os.getenv("EMBEDDING_MODEL") or EMBEDDING_MODEL).strip()


def _embed_sentence_transformers(texts: list[str]) -> list[list[float]]:
    global _sentence_transformer

    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer

        _sentence_transformer = SentenceTransformer(_model_name())

    vectors = _sentence_transformer.encode(
        texts,
        batch_size=LOCAL_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [[float(value) for value in vector] for vector in vectors]


def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI()
    model = os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"
    vectors: list[list[float]] = []
    for start in range(0, len(texts), API_BATCH_SIZE):
        batch = texts[start : start + API_BATCH_SIZE]
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors


def _embed_gemini(texts: list[str]) -> list[list[float]]:
    from google import genai

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    model = os.getenv("EMBEDDING_MODEL") or "gemini-embedding-001"
    vectors: list[list[float]] = []
    for start in range(0, len(texts), API_BATCH_SIZE):
        batch = texts[start : start + API_BATCH_SIZE]
        response = client.models.embed_content(model=model, contents=batch)
        vectors.extend(list(item.values) for item in response.embeddings)
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed danh sách text bằng provider trong ``EMBEDDING_PROVIDER``.

    Đây là điểm vào duy nhất của cả repo cho embedding — Task 5 import lại đúng
    hàm này để query vector và document vector nằm cùng không gian.
    """
    if not texts:
        return []

    provider = _provider()
    if provider == "sentence_transformers":
        return _embed_sentence_transformers(texts)
    if provider == "openai":
        return _embed_openai(texts)
    if provider == "gemini":
        return _embed_gemini(texts)
    raise ValueError(
        f"EMBEDDING_PROVIDER khong ho tro: {provider!r}. "
        "Dung sentence_transformers | openai | gemini."
    )


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _extract_title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if match and match.group(1).strip():
        return match.group(1).strip()
    return fallback


def _extract_url(text: str) -> str | None:
    match = re.search(r"^\*\*Source:\*\*\s+(https?://\S+)", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def load_documents() -> list[dict]:
    """Đọc Markdown trong ``data/standardized`` và trả về danh sách Document."""
    documents: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            continue

        relative = path.relative_to(STANDARDIZED_DIR)
        doc_type = "legal" if "legal" in relative.parts else "news"
        documents.append(
            {
                "id": relative.as_posix(),
                "content": content,
                "metadata": {
                    "source": path.name,
                    "title": _extract_title(content, fallback=path.stem),
                    "doc_type": doc_type,
                    "url": _extract_url(content),
                },
            }
        )
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id ổn định và ``chunk_index``."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[dict] = []
    for document in documents:
        index = 0
        for text in splitter.split_text(document["content"]):
            if not text.strip():
                # Contract yêu cầu content khác rỗng; bỏ chunk trắng và giữ
                # chunk_index liên tục.
                continue
            chunks.append(
                {
                    "id": f"{document['id']}::chunk-{index}",
                    "content": text,
                    "metadata": {**document["metadata"], "chunk_index": index},
                }
            )
            index += 1
    return chunks


def load_chunks() -> list[dict]:
    """Corpus dùng chung cho dense (Task 5) và BM25 (Task 6)."""
    return chunk_documents(load_documents())


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk, giữ nguyên các field còn lại."""
    if not chunks:
        return []

    vectors = embed_texts([chunk["content"] for chunk in chunks])
    if len(vectors) != len(chunks):
        raise RuntimeError(
            f"embed_texts tra ve {len(vectors)} vector cho {len(chunks)} chunk"
        )
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    return chunks


def _chroma_metadata(metadata: dict) -> dict:
    """Chroma từ chối metadata value ``None`` -> ép về chuỗi rỗng."""
    return {key: ("" if value is None else value) for key, value in metadata.items()}


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks vào ChromaDB."""
    if not chunks:
        print("Nothing to index")
        return

    collection = get_collection()
    for start in range(0, len(chunks), UPSERT_BATCH_SIZE):
        batch = chunks[start : start + UPSERT_BATCH_SIZE]
        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            metadatas=[_chroma_metadata(chunk["metadata"]) for chunk in batch],
        )
    print(f"Collection {COLLECTION_NAME} now holds {collection.count()} chunks")


def run_pipeline() -> None:
    """Chạy load, chunk, embed và index."""
    documents = load_documents()
    print(f"Loaded {len(documents)} documents from {STANDARDIZED_DIR}")

    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    if not chunks:
        raise RuntimeError("Khong co chunk nao — chay Task 1-3 truoc.")

    print(f"Embedding with provider={_provider()} model={_model_name()}")
    embedded_chunks = embed_chunks(chunks)

    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks")


if __name__ == "__main__":
    run_pipeline()
