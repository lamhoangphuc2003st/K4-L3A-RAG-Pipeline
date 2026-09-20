"""
Task 10 — Generation có citation.

Hướng dẫn:
    1. Retrieve top-k chunks.
    2. Reorder để giảm lost-in-the-middle.
    3. Format context kèm title và source.
    4. Gọi provider được chọn trong .env.
    5. Trả answer, sources và retrieval_source.

Nếu context không đủ hoặc provider lỗi, trả safe refusal; không bịa thông tin.
"""

import os
from dotenv import load_dotenv

from .task9_retrieval_pipeline import retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower().strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()

SYSTEM_PROMPT = """Bạn là trợ lý AI trả lời câu hỏi dựa trên các tài liệu được cung cấp.
QUY TẮC BẮT BUỘC:
1. Trả lời CHỈ dựa trên thông tin có trong phần Context dưới đây. KHÔNG sử dụng kiến thức bên ngoài, KHÔNG suy diễn hoặc bịa đặt thông tin.
2. Mỗi thông tin/khẳng định trong câu trả lời PHẢI có trích dẫn nguồn tương ứng bằng cú pháp [Document X], ví dụ: [Document 1], [Document 2].
3. Nếu trong Context không có đủ thông tin hoặc câu hỏi nằm ngoài nội dung tài liệu, hãy trả lời chính xác câu sau:
"Tôi không thể xác minh thông tin này từ nguồn hiện có."
4. Trình bày rõ ràng, mạch lạc, trung thực với ngữ cảnh."""

SAFE_REFUSAL_ANSWER = "Tôi không thể xác minh thông tin này từ nguồn hiện có."


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Đưa chunks quan trọng về đầu và cuối context (chống lost-in-the-middle).

    Bảo toàn bản gốc của danh sách chunks truyền vào và không làm thay đổi các phần tử.
    """
    if not chunks:
        return []
    if len(chunks) <= 2:
        return list(chunks)

    # Đặt chunk có score cao nhất xen kẽ ở đầu và cuối
    front = chunks[::2]
    back = chunks[1::2]
    return front + back[::-1]


def format_context(chunks: list[dict]) -> str:
    """Tạo context có title và source label để LLM dễ dàng trích dẫn."""
    parts = []
    for index, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        title = meta.get("title", "Không có tiêu đề")
        source = meta.get("source", "Nguồn không xác định")
        content = chunk.get("content", "").strip()
        parts.append(
            f"[Document {index} | Title: {title} | Source: {source}]\n{content}"
        )
    return "\n\n---\n\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Gọi OpenAI, Gemini hoặc Anthropic theo cấu hình LLM_PROVIDER.

    Dùng LLM_MODEL và trả về text thuần cho cả ba nhánh.
    """
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER).lower().strip()
    model_name = os.getenv("LLM_MODEL", LLM_MODEL).strip()

    if provider == "openai":
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY chưa được cấu hình trong .env")
        client = OpenAI(api_key=api_key)
        model = model_name or "gpt-4o-mini"
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        return response.choices[0].message.content or ""

    elif provider == "gemini":
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình trong .env")
        client = genai.Client(api_key=api_key)
        model = model_name or "gemini-2.0-flash"
        response = client.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=TEMPERATURE,
                top_p=TOP_P,
            ),
        )
        return response.text or ""

    elif provider == "anthropic":
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY chưa được cấu hình trong .env")
        client = Anthropic(api_key=api_key)
        model = model_name or "claude-3-5-haiku-20241022"
        response = client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=TEMPERATURE,
            max_tokens=1024,
        )
        return response.content[0].text if response.content else ""

    else:
        raise ValueError(f"LLM_PROVIDER không được hỗ trợ: '{provider}'")


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Trả về GenerationResult:
    {
        'answer': str,
        'sources': list[SearchResult],
        'retrieval_source': 'hybrid' | 'pageindex' | 'none'
    }
    """
    try:
        chunks = retrieve(query, top_k=top_k)
    except Exception:
        chunks = []

    if not chunks:
        return {
            "answer": SAFE_REFUSAL_ANSWER,
            "sources": [],
            "retrieval_source": "none",
        }

    reordered = reorder_for_llm(chunks)
    context_str = format_context(reordered)
    user_prompt = f"Context:\n{context_str}\n\nCâu hỏi: {query}\n\nTrả lời:"

    try:
        answer = call_llm(SYSTEM_PROMPT, user_prompt)
        if not answer or not answer.strip():
            answer = SAFE_REFUSAL_ANSWER
    except Exception:
        # Nếu LLM provider lỗi (hết quota, timeout, network), trả safe refusal không để UI crash
        return {
            "answer": SAFE_REFUSAL_ANSWER,
            "sources": [],
            "retrieval_source": "none",
        }

    # Xác định retrieval_source theo contract
    raw_source = chunks[0].get("retrieval_method", "hybrid")
    if raw_source in {"dense", "bm25", "hybrid"}:
        retrieval_source = "hybrid"
    elif raw_source == "pageindex":
        retrieval_source = "pageindex"
    else:
        retrieval_source = "none"

    return {
        "answer": answer.strip(),
        "sources": chunks,  # Giữ nguyên danh sách gốc đã sort giảm dần theo score
        "retrieval_source": retrieval_source,
    }


if __name__ == "__main__":
    print(generate_with_citation("Thời gian phục vụ của thư viện như thế nào?"))
