# Individual contribution report

## Thông tin

- Họ và tên: Nguyễn Văn Tài
- Mã học viên: 2A202603004
- Nhóm: K4 — L3A, role **Data**
- Repository/branch: `lamhoangphuc2003st/K4-L3A-RAG-Pipeline` — `feat/data` → `dev`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Task 1 — thu thập tài liệu chính sách | Khảo sát và xác thực 11 URL công khai, chốt 7 nguồn PDF (học phí, học bổng ×2, ký túc xá ×3, sổ tay sinh viên). Viết `download_documents()` kiểm tra magic bytes `%PDF` + size > 1KB, tự xoá file rác, bỏ qua file đã tải, raise khi < 3 tài liệu hợp lệ | `src/task1_collect_legal_docs.py`, `data/landing/legal/*.pdf` — commit `c530a56` | Done |
| Task 2 — crawl bài viết | Chốt 9 URL đã kiểm tra HTTP 200, viết `crawl_article()` dùng Crawl4AI với browser dùng chung, fallback `requests` + MarkItDown, `validate_article()` chặn bài thiếu key hoặc < 200 ký tự | `src/task2_crawl_news.py`, `data/landing/news/*.json` — commit `c530a56`, `03e5ba8`, `c55017a`; dữ liệu `80754bf` | Done |
| Task 3 — chuẩn hoá Markdown | Convert PDF/DOCX bằng MarkItDown, ghép metadata header cho JSON news, `write_if_long_enough()` chặn file dưới 200 ký tự, `remove_orphans()` xoá `.md` mất file nguồn, `drop_toc_and_form_lines()` bỏ mục lục/mẫu đơn/khung bảng rỗng | `src/task3_convert_markdown.py`, `data/standardized/{legal,news}/*.md` — commit `c530a56`, `c55017a`; dữ liệu `80754bf` | Done |
| Task 4 — chunk, embed, index | `load_documents()` (parse title từ heading, url từ header `**Source:**`), `chunk_documents()` id ổn định, `embed_texts()` dispatch 3 provider + cache model, `get_collection()` cosine, `index_to_vectorstore()` upsert batch 500 + xoá chunk stale | `src/task4_chunking_indexing.py` — commit `c530a56`, `c55017a` | Done |
| Bàn giao cho Retrieval | Thêm `load_chunks()` = `chunk_documents(load_documents())` làm corpus dùng chung, để Task 6 (BM25) không tự nạp corpus khác Task 5 (dense) | `src/task4_chunking_indexing.py::load_chunks` | Done |
| Môi trường chạy được | Dựng `.venv` Python 3.11.16, xử lý 3 lỗi setup (mục "Lỗi đã phát hiện") | `.env` (không commit), `pyproject.toml` giữ nguyên | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Xác định thân bài theo **tỉ lệ text**, không theo thẻ HTML đầu tiên: chọn khối `<article>`/`<main>` có nhiều text nhất, nhưng chỉ dùng nó khi nó chiếm ≥ 30% text của trang (`MIN_REGION_TEXT_SHARE`); còn lại thì giữ toàn trang và lọc theo mật độ link.
   **Lý do/evidence:** Tôi đã viết sai hai lần trước khi ra được quy tắc này, cả hai lần đều phát hiện bằng cách đọc dữ liệu thật chứ không phải đọc code. Lần đầu lấy `<article>` đầu tiên → `tuoitre.vn` có 3 thẻ `<article>` ~2KB đều là card "tin liên quan", thân bài thật nằm trong `<main>`, kết quả bài chỉ còn **497 ký tự** toàn teaser. Lần hai lấy khối dài nhất vô điều kiện → `giaoducthoidai.vn` có **38 thẻ `<article>`** teaser (dài nhất 359 ký tự) và **không có `<main>`**, nên document thu được là một bài về *Tổng Bí thư dự Đại hội đồng Liên hợp quốc* — sai hoàn toàn chủ đề và sẽ thành document rác trong corpus. Với ràng buộc 30%, bài này trở lại đúng nội dung học bổng ĐH Kiên Giang (19780 ký tự).
   **Trade-off:** Ngưỡng 30% là số chọn tay, tôi chưa đo trên đủ nhiều site để biết nó tối ưu; nó cũng đánh đổi theo hướng "thà giữ thêm boilerplate còn hơn mất thân bài", nên với trang có sidebar lớn thì vẫn còn rác và phải dựa vào bước lọc mật độ link phía sau.

2. **Quyết định:** `embed_texts()` trong Task 4 là điểm vào embedding duy nhất của repo, có cache model ở module level; các task khác import lại chứ không tự tạo `SentenceTransformer`.
   **Lý do/evidence:** `WORK_DIVISION.md` cảnh báo "không để tồn tại model thứ hai trong repo" — nếu Task 5 tự khởi tạo model thì query vector và document vector có thể lệch không gian (khác model hoặc khác `normalize_embeddings`), làm cosine score mất ý nghĩa và Task 9 hiệu chỉnh threshold trên số sai. Quyết định này trả cổ tức ngay trong buổi: khi bge-m3 2.27GB tải stall và nhóm phải đổi sang OpenAI `text-embedding-3-small`, việc chuyển provider chỉ cần **đổi 2 dòng trong `.env`**, không sửa một dòng code nào ở Task 4/5/6 — kể cả khi số chiều đổi từ 1024 sang 1536.
   **Trade-off:** Dùng biến global `_sentence_transformer`, không thread-safe — chấp nhận được vì pipeline chạy tuần tự, nhưng nếu sau này Streamlit gọi song song nhiều request thì phải bọc lock hoặc chuyển sang `functools.lru_cache`. Ngoài ra provider API tính tiền theo lần gọi, nên mỗi lần re-index là một lần trả phí, khác với model local chạy miễn phí — đây là lý do bước xoá chunk stale quan trọng: nó cho phép re-index đúng thay vì phải xoá sạch `chroma_db` và embed lại từ đầu.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng:
  - Xác thực nguồn trước khi đưa vào code: `curl` kiểm tra HTTP status + `content_type` + magic bytes cho 11 PDF/URL ứng viên, chỉ giữ nguồn trả đúng `application/pdf` / HTTP 200.
  - `pytest tests/test_contracts.py -q` — phần liên quan tôi: `test_public_function_signatures_are_stable` (`load_documents` không tham số, `chunk_documents(documents)`).
  - `pytest tests/test_acceptance.py -q` — 3 test thuộc phần tôi: ≥3 PDF > 1KB, ≥5 JSON đủ 4 key, ≥3 legal + ≥5 news Markdown mỗi file ≥ 200 ký tự.
  - `python -m src.task4_chunking_indexing` — kiểm tra số chunk > 0 và chạy lần 2 không làm tăng `collection.count()` (bằng chứng id ổn định).
- Kết quả trước/sau nếu có:
  - Corpus cuối: **14 document** (7 legal + 7 news) → **1237 chunk**, `1237/1237` id unique, toàn bộ pass `validate_document(..., require_chunk=True)`.
  - Idempotent: chạy `python -m src.task4_chunking_indexing` lần 2 → `collection.count()` vẫn giữ nguyên, không nhân đôi.
  - Chất lượng retrieval trước/sau khi lọc boilerplate, cùng query `"muc tran hoc phi dai hoc cong lap nam hoc 2026-2027"`: **trước** top-2 là 2 dòng link menu của news, bảng học phí trong nghị định chỉ xếp #3; **sau** bảng học phí lên #1.
  - Mật độ dòng khung bảng trong legal sau khi lọc: `nghidinh` 2%→1%, `sotay-vnua` 8%→4%, `hcmiu` 1%→0%, `hmu` 45%→38%.
  - Dense score đo được để Eval hiệu chỉnh `SCORE_THRESHOLD`: in-domain best **0.47–0.53**, out-of-domain (`"thu do Nhat Ban la gi"`) best **0.41**.
  - `pytest -q`: từ 7 failed → **5 failed, 15 passed**; 5 test còn đỏ đều thuộc Evaluation/Integration (`golden_dataset.json`, `RESULT.md`, `retrieve()` Task 9), không còn test nào thuộc Data.
- Lỗi đã phát hiện và cách xử lý:
  - **Python mặc định 3.14.7 vượt `requires-python = ">=3.10,<3.14"`** → dựng venv bằng Python 3.11.16 thay vì `python -m venv`.
  - **`uv pip install` fail: `Failed to download pandas==3.0.6 … network timeout`** do `UV_HTTP_TIMEOUT` mặc định 30s không đủ cho wheel lớn khi tải 13 package song song → chạy lại với `UV_HTTP_TIMEOUT=600` và `UV_CONCURRENT_DOWNLOADS=4`.
  - **`uv venv` không seed `pip`** → `python -m pip` và `python -m playwright` báo `No module named pip`, phải seed `pip/setuptools/wheel` vào venv.
  - **Nguồn trả HTML thay vì PDF** (`geology.hus.vnu.edu.vn`, 1484 byte, bắt đầu bằng `<!DO`) mà HTTP vẫn 200 → `is_valid_pdf()` kiểm tra magic bytes `%PDF` rồi xoá file, thay vì tin vào status code.
  - **ChromaDB từ chối metadata value `None`** trong khi `contracts.validate_document` lại cho phép `url: None` → giữ `None` ở tầng contract, chỉ ép `None` → `""` tại biên ghi Chroma trong `_chroma_metadata()`; không sửa contract.
  - **`upsert` không xoá chunk cũ** → khi một document ngắn lại sau khi lọc boilerplate, các `chunk-index` cao trước đó vẫn nằm trong collection và vẫn được retrieve. Thêm bước xoá stale id trong `index_to_vectorstore()`; lần chạy đầu sau fix xoá **127 chunk**, lần sau xoá thêm **56 chunk**.
  - **Ngưỡng "200 ký tự" đếm được cả rác** → 2 trang listing thông báo (`www.ktxhcm.edu.vn` còn 72 ký tự văn xuôi, `tuyensinh.ufm.edu.vn` còn 179) vẫn vượt ngưỡng tổng ký tự nhờ heading + dòng ngày, và đã thành document vô nghĩa trong corpus. Đổi `validate_article()` sang đếm **ký tự văn xuôi** (bỏ dòng ngắn và dòng mở đầu bằng `#*|-+>`).
  - **File Markdown mồ côi** → khi URL bị loại ở lần chạy sau, `article_09.md` vẫn nằm lại trong `standardized/news` và bị index. Thêm `remove_orphans()`.
  - **Regex lọc link không khớp ngoặc lồng** `[[Thông báo] Hướng dẫn](/vi/...)` nên menu vẫn lọt vào embedding → đổi sang lọc theo **mật độ link** trên mỗi dòng (`MAX_LINK_DENSITY = 0.55`).
  - **`SentenceTransformer` tải bge-m3 2.27GB bị stall** ở 0 byte trên mạng của tôi (đã fail trước đó với `pandas` và Chromium 195MB). Nhóm đổi sang `EMBEDDING_PROVIDER=openai` + `text-embedding-3-small` — `embed_texts()` đã dispatch sẵn nên **không phải sửa code**, chỉ đổi 2 dòng `.env`.

## Điều còn hạn chế

- Một hạn chế cụ thể của phần tôi làm: `quy-che-sinh-vien-noi-tru-hmu.pdf` bị lỗi encoding khi extract — dấu tiếng Việt tách khỏi chữ (`ngư iờ` thay vì `người`, `ÐNƠ`) và **38% số dòng vẫn là khung bảng** sau khi lọc, cao hơn hẳn 6 tài liệu còn lại (0–17%). Tôi chọn giữ lại vì nó là một trong ba nguồn nội quy KTX, nhưng phần nội dung dạng bảng của nó gần như không retrieve được đúng. Sổ tay VNUA cũng chiếm tỉ trọng lớn bất thường trong corpus (4262/7308 dòng legal) nên kết quả dense nghiêng về tài liệu này.
- Hạn chế thứ hai: **Crawl4AI chưa từng chạy thật trên dữ liệu này** — Chromium tải fail ở 70% (`ECONNRESET`) nên toàn bộ 7 bài news đi qua nhánh fallback `requests` + MarkItDown. Nhánh fallback không chạy JavaScript, nên nếu nguồn render phía client thì sẽ không lấy được nội dung; đường crawl chính vẫn chưa được kiểm chứng.
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện: chunk văn bản pháp quy theo cấu trúc **Điều/Khoản** thay vì cắt cứng 500 ký tự với overlap 50 — hiện một Điều dài có thể bị cắt giữa câu, làm chunk mất ngữ cảnh và citation trỏ vào đoạn không đủ nghĩa.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 20/09/2026
- Tên thành viên: Nguyễn Văn Tài
