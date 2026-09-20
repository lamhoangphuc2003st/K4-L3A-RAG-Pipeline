# Individual contribution report

## Thông tin

- Họ và tên: Nguyễn Văn Tài
- Mã học viên: 2A202603004
- Nhóm: K4 — L3A, role **Data**
- Repository/branch: `lamhoangphuc2003st/K4-L3A-RAG-Pipeline` — `feat/data` → `dev`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Task 1 — thu thập tài liệu chính sách | Khảo sát và xác thực 11 URL công khai, chốt 7 nguồn PDF (học phí, học bổng ×2, ký túc xá ×3, sổ tay sinh viên). Viết `download_documents()` kiểm tra magic bytes `%PDF` + size > 1KB, tự xoá file rác, bỏ qua file đã tải, raise khi < 3 tài liệu hợp lệ | `src/task1_collect_legal_docs.py`, `data/landing/legal/*.pdf` — commit `⟨hash⟩` | Done |
| Task 2 — crawl bài viết | Chốt 9 URL đã kiểm tra HTTP 200, viết `crawl_article()` dùng Crawl4AI với browser dùng chung, fallback `requests` + MarkItDown, `validate_article()` chặn bài thiếu key hoặc < 200 ký tự | `src/task2_crawl_news.py`, `data/landing/news/*.json` — commit `⟨hash⟩` | Done |
| Task 3 — chuẩn hoá Markdown | Convert PDF/DOCX bằng MarkItDown, ghép metadata header cho JSON news, `write_if_long_enough()` loại PDF không có text layer và xoá bản cũ để không lọt vào index | `src/task3_convert_markdown.py`, `data/standardized/{legal,news}/*.md` — commit `⟨hash⟩` | Done |
| Task 4 — chunk, embed, index | `load_documents()` (parse title từ heading, url từ header `**Source:**`), `chunk_documents()` id ổn định, `embed_texts()` dispatch 3 provider + cache model, `get_collection()` cosine, `index_to_vectorstore()` upsert theo batch 500 | `src/task4_chunking_indexing.py` — commit `⟨hash⟩` | Done |
| Bàn giao cho Retrieval | Thêm `load_chunks()` = `chunk_documents(load_documents())` làm corpus dùng chung, để Task 6 (BM25) không tự nạp corpus khác Task 5 (dense) | `src/task4_chunking_indexing.py::load_chunks` | Done |
| Môi trường chạy được | Dựng `.venv` Python 3.11.16, xử lý 3 lỗi setup (mục "Lỗi đã phát hiện") | `.env` (không commit), `pyproject.toml` giữ nguyên | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Crawl 2 tầng — Crawl4AI/Chromium là đường chính, tự rơi về `requests` + MarkItDown khi browser không mở được hoặc site chặn; đồng thời mở Chromium **một lần** trong `crawl_all()` rồi truyền vào từng lần `crawl_article()`.
   **Lý do/evidence:** Khi xác thực nguồn, 4/11 URL chết vì lý do hạ tầng chứ không phải nội dung: `baodautu.vn` lỗi `CRYPT_E_REVOCATION_OFFLINE`, `ktx.ueh.edu.vn` lỗi `SEC_E_CERT_EXPIRED`, `xettuyen.bdu.edu.vn` bị reset kết nối, `geology.hus.vnu.edu.vn` trả về HTML 1484 byte thay vì PDF. Nếu chỉ có một đường crawl thì mỗi nguồn chết là mất một bài, trong khi đề yêu cầu tối thiểu 5 bài.
   **Trade-off:** Fallback không chạy JavaScript, nên site render phía client sẽ ra ít text hơn Crawl4AI; bù lại `validate_article()` chặn ngay bài < 200 ký tự nên dữ liệu rác không vào index. Skeleton gốc mở một `AsyncWebCrawler` cho mỗi URL — đúng nhưng tốn ~9 lần khởi động Chromium; tôi đổi sang browser dùng chung và phải thêm tham số optional `crawler` vào `crawl_article()`.

2. **Quyết định:** `embed_texts()` trong Task 4 là điểm vào embedding duy nhất của repo, có cache model ở module level; các task khác import lại chứ không tự tạo `SentenceTransformer`.
   **Lý do/evidence:** `WORK_DIVISION.md` cảnh báo "không để tồn tại model thứ hai trong repo" — nếu Task 5 tự khởi tạo model thì query vector và document vector có thể lệch không gian (khác model hoặc khác `normalize_embeddings`), làm cosine score mất ý nghĩa và Task 9 hiệu chỉnh threshold trên số sai. Cache model cũng tránh nạp lại bge-m3 (~2GB) ở mỗi lần gọi.
   **Trade-off:** Dùng biến global `_sentence_transformer`, không thread-safe — chấp nhận được vì pipeline chạy tuần tự, nhưng nếu sau này Streamlit gọi song song nhiều request thì phải bọc lock hoặc chuyển sang `functools.lru_cache`.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng:
  - Xác thực nguồn trước khi đưa vào code: `curl` kiểm tra HTTP status + `content_type` + magic bytes cho 11 PDF/URL ứng viên, chỉ giữ nguồn trả đúng `application/pdf` / HTTP 200.
  - `pytest tests/test_contracts.py -q` — phần liên quan tôi: `test_public_function_signatures_are_stable` (`load_documents` không tham số, `chunk_documents(documents)`).
  - `pytest tests/test_acceptance.py -q` — 3 test thuộc phần tôi: ≥3 PDF > 1KB, ≥5 JSON đủ 4 key, ≥3 legal + ≥5 news Markdown mỗi file ≥ 200 ký tự.
  - `python -m src.task4_chunking_indexing` — kiểm tra số chunk > 0 và chạy lần 2 không làm tăng `collection.count()` (bằng chứng id ổn định).
- Kết quả trước/sau nếu có: `⟨số document / số chunk / collection.count() sau 2 lần chạy — điền sau khi chạy pipeline⟩`
- Lỗi đã phát hiện và cách xử lý:
  - **Python mặc định 3.14.7 vượt `requires-python = ">=3.10,<3.14"`** → dựng venv bằng Python 3.11.16 thay vì `python -m venv`.
  - **`uv pip install` fail: `Failed to download pandas==3.0.6 … network timeout`** do `UV_HTTP_TIMEOUT` mặc định 30s không đủ cho wheel lớn khi tải 13 package song song → chạy lại với `UV_HTTP_TIMEOUT=600` và `UV_CONCURRENT_DOWNLOADS=4`.
  - **`uv venv` không seed `pip`** → `python -m pip` và `python -m playwright` báo `No module named pip`, phải seed `pip/setuptools/wheel` vào venv.
  - **Nguồn trả HTML thay vì PDF** (`geology.hus.vnu.edu.vn`, 1484 byte, bắt đầu bằng `<!DO`) mà HTTP vẫn 200 → `is_valid_pdf()` kiểm tra magic bytes `%PDF` rồi xoá file, thay vì tin vào status code.
  - **ChromaDB từ chối metadata value `None`** trong khi `contracts.validate_document` lại cho phép `url: None` → giữ `None` ở tầng contract, chỉ ép `None` → `""` tại biên ghi Chroma trong `_chroma_metadata()`; không sửa contract.

## Điều còn hạn chế

- Một hạn chế cụ thể của phần tôi làm: PDF scan (không có text layer) bị `convert_legal_docs()` loại thẳng thay vì OCR, nên một số văn bản đã tải về vẫn không vào được corpus — số tài liệu thực sự dùng được ít hơn số file trong `data/landing/legal/`.
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện: chunk văn bản pháp quy theo cấu trúc **Điều/Khoản** thay vì cắt cứng 500 ký tự với overlap 50 — hiện một Điều dài có thể bị cắt giữa câu, làm chunk mất ngữ cảnh và citation trỏ vào đoạn không đủ nghĩa.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 20/09/2026
- Tên thành viên: Nguyễn Văn Tài
