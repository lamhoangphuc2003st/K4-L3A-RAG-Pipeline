import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import generate_with_citation


load_dotenv()

st.set_page_config(
    page_title="Hệ thống Hỏi đáp Dịch vụ Đại học (RAG Chatbot)",
    page_icon="🎓",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("⚙️ Cấu hình RAG")
    st.caption("Dịch vụ đại học: Học phí, thư viện, quy chế mượn trả & tra cứu tài liệu")
    top_k = st.slider("Số chunks (top_k)", min_value=3, max_value=10, value=5, step=1)

    st.markdown("---")
    st.markdown("### ℹ️ Thông tin Pipeline")
    st.markdown(
        "- **Hybrid Retrieval:** Dense (BGE-M3) + Sparse (BM25)\n"
        "- **Fusion:** Reciprocal Rank Fusion (RRF)\n"
        "- **Fallback:** Vectorless / PageIndex\n"
        "- **Citation:** Tự động đối chiếu nguồn và safe refusal khi không đủ dữ liệu."
    )

    if st.button("🧹 Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("🎓 RAG Chatbot — Dịch vụ Đại học")
st.caption(
    "Trợ lý AI hỗ trợ giải đáp quy định, chính sách, học phí và dịch vụ thư viện sinh viên. "
    "Mọi thông tin đều được trích dẫn trực tiếp từ văn bản chính thức."
)


def render_sources(sources: list[dict], retrieval_source: str | None = None):
    """Hiển thị thông tin trích dẫn, score và phương thức tìm kiếm."""
    if not sources:
        return

    with st.expander(f"📚 Nguồn trích dẫn ({len(sources)} tài liệu) — Phương thức: `{retrieval_source or 'hybrid'}`", expanded=False):
        for idx, src in enumerate(sources, 1):
            metadata = src.get("metadata", {})
            title = metadata.get("title", "Không có tiêu đề")
            source = metadata.get("source", "Nguồn không xác định")
            score = src.get("score", 0.0)
            method = src.get("retrieval_method", "N/A")
            url = metadata.get("url")

            st.markdown(f"**[{idx}] {title}** (`{source}`)")
            url_text = f"[Xem liên kết]({url})" if url else "Tài liệu nội bộ"
            st.caption(f"Phương thức: `{method}` | Điểm: `{score:.4f}` | {url_text}")
            with st.container():
                st.code(src.get("content", "").strip(), language="markdown")
            if idx < len(sources):
                st.divider()


# Hiển thị lại toàn bộ lịch sử trò chuyện
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "sources" in message:
            render_sources(message["sources"], message.get("retrieval_source"))

query = st.chat_input("Nhập câu hỏi về quy định, dịch vụ hoặc thư viện...")

if query:
    # 1. Thêm câu hỏi của user vào giao diện & session state
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # 2. Sinh câu trả lời từ RAG Pipeline
    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm tài liệu và sinh câu trả lời có trích dẫn..."):
            result = generate_with_citation(query, top_k=top_k)
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            retrieval_source = result.get("retrieval_source", "none")

            st.markdown(answer)
            if sources:
                render_sources(sources, retrieval_source)

    # 3. Lưu lại câu trả lời và sources vào session state để giữ nguyên khi render lại
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": sources,
        "retrieval_source": retrieval_source,
    })
