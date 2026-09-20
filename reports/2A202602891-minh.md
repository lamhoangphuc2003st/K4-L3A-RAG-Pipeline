# Individual contribution report

---

## Thông tin

- Họ và tên: Nguyễn Đức Minh
- Mã học viên: 2A202602891
- Nhóm: K4 — L3A (Nhóm 4)
- Repository/branch: `K4-L3A-RAG-Pipeline` / `feat/generation-ui`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Task 10 — Generation & Citation | Xây dựng pipeline tạo câu trả lời với context reordering, trích dẫn citation kiểm chứng được, xử lý safe refusal và dispatch đa provider LLM (OpenAI, Gemini, Anthropic) | `src/task10_generation.py` | Done |
| App Chatbot Streamlit | Xây dựng giao diện Chatbot tương tác, hiển thị câu trả lời kèm citation, nguồn tài liệu (sources), độ tương đồng (score), phương thức truy xuất (retrieval method) và lưu lịch sử phiên chat | `app.py` | Done |
| Kiểm thử Contract Task 10 | Kiểm thử tính ổn định của hàm `reorder_for_llm`, `format_context`, `generate_with_citation` bảo toàn ID và pass `test_contracts.py` | `tests/test_contracts.py` | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Áp dụng thuật toán reordering (Lost-in-the-middle) đưa các chunk có score cao nhất phân bổ về đầu và cuối danh sách context (`front = chunks[::2]`, `back = chunks[1::2]`, trả về `front + back[::-1]`).  
   **Lý do/evidence:** Nghiên cứu cho thấy LLM thường chú ý nhiều nhất đến phần đầu và phần cuối của prompt context và dễ bỏ qua thông tin nằm ở giữa.  
   **Trade-off:** Thứ tự trong context đưa vào LLM bị xáo trộn nhẹ so với thứ tự rank ban đầu, nhưng giải quyết triệt để vấn đề mất tập trung của model khi context dài. Danh sách `sources` trả về cho hợp đồng và UI vẫn được giữ nguyên thứ tự giảm dần theo điểm để đảm bảo contract test pass.

2. **Quyết định:** Triển khai cơ chế Safe Refusal hai lớp (bảo vệ ở cả tầng retrieval và tầng LLM generation khi thiếu dữ liệu hoặc khi provider gặp sự cố).  
   **Lý do/evidence:** Tránh tình trạng ảo giác (hallucination) của LLM khi gặp câu hỏi ngoài phạm vi dữ liệu hoặc câu hỏi bẫy; đồng thời giữ cho UI Streamlit không bao giờ bị crash khi LLM provider hết quota hoặc timeout.  
   **Trade-off:** Chatbot sẽ từ chối trả lời nếu độ tự tin hoặc bằng chứng trong tài liệu không đủ, ưu tiên tính chính xác và an toàn thông tin hơn là cố gắng suy đoán câu trả lời.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng:
  - Chạy test hợp đồng: `pytest tests/test_contracts.py -k "reorder or generation or public_function" -q`
  - Query in-domain: "Thời gian phục vụ và mượn trả tài liệu của thư viện như thế nào?" -> Chatbot trích dẫn chính xác [Document 1], hiển thị score và nguồn.
  - Query out-of-domain / query bẫy: "Cách đăng ký thi bằng lái xe máy tại trường?" -> Hệ thống kích hoạt safe refusal: "Tôi không thể xác minh thông tin này từ nguồn hiện có." kèm `retrieval_source: none`.
- Kết quả trước/sau nếu có: Trước khi reorder, câu trả lời đôi khi bỏ sót thông tin của các chunk nằm giữa danh sách; sau khi reorder, thông tin được tổng hợp đầy đủ và citation chuẩn xác hơn.
- Lỗi đã phát hiện và cách xử lý: Khi trả về `sources` cho `GenerationResult`, ban đầu truyền nhầm danh sách `reordered` khiến `validate_search_results` báo lỗi không sort giảm dần theo score; đã sửa lại truyền danh sách `chunks` gốc cho `sources` và chỉ dùng `reordered` để format prompt context.

## Điều còn hạn chế

- Một hạn chế cụ thể của phần tôi làm: Hiện tại UI Streamlit hiển thị citation dưới dạng danh sách expander nguồn chi tiết, chưa làm được tính năng tương tác highlight trực tiếp câu văn trong đoạn trích nguồn (source highlighting).
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện: Bổ sung Conversation Memory (lưu nhớ ngữ cảnh hội thoại đa lượt) và highlight câu trích dẫn trực quan trong UI.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 2026-09-20
- Tên thành viên: Nguyễn Đức Minh
