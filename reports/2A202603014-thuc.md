# Individual contribution report

## Thông tin

- Họ và tên: Nguyễn Đăng Thực
- Mã học viên: 2A202603014
- Nhóm: K4 — L3A, đề tài *Dịch vụ đại học* (học phí, học bổng, ký túc xá, thư viện, đăng ký học phần)
- Repository/branch: `K4-L3A-RAG-Pipeline` — role **Retrieval**, nhánh `feat/retrieval`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Task 7 — Reciprocal Rank Fusion | Fusion theo rank (`1/(k+rank)`, rank từ 1), khử ID trùng trong cùng list, tie-break theo ID cho kết quả tái lập, copy dict trước khi ghi đè nên không mutate input, output `retrieval_method="hybrid"` | `src/task7_reranking.py` — `df65fc1` | Done |
| Task 5 — Dense search | Query ChromaDB qua đúng `embed_texts()`/`get_collection()` của Task 4, đổi cosine distance → similarity `max(0.0, 1.0 - distance)`, khử ID trùng, sort giảm dần, cắt `top_k` | `src/task5_semantic_search.py` — `a5d7973` | Done |
| Task 6 — BM25 lexical search | Nạp `CORPUS` lazy bằng `load_chunks()` của Task 4, tokenizer Unicode giữ dấu tiếng Việt + giữ nguyên mã văn bản, lọc theo token overlap, cache index theo corpus | `src/task6_lexical_search.py` — `73db7d6` | Done |
| Contract tests phần retrieval | 4/4 test liên quan xanh: `test_public_function_signatures_are_stable`, `test_semantic_search_uses_shared_embedding_and_contract`, `test_lexical_search_returns_bm25_contract`, `test_rrf_uses_rank_deduplicates_and_marks_hybrid` | `pytest tests/test_contracts.py -k "signatures or semantic or lexical or rrf"` | Done |
| Bàn giao cho Task 9 | Giữ đúng chữ ký `semantic_search(query, top_k)`, `lexical_search(query, top_k)`, `rerank_rrf(ranked_lists, top_k, k)` như `retrieve()` gọi | — | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** BM25 lọc kết quả theo **token overlap giữa query và chunk**, không lọc bằng `score > 0` như gợi ý trong scaffold.
   **Lý do/evidence:** `BM25Okapi` tính `idf = log(N - df + 0.5) - log(df + 0.5)`. Với corpus nhỏ (N=2, df=1) idf bằng đúng 0 nên chunk khớp hoàn toàn vẫn được 0 điểm và bị loại oan — `test_lexical_search_returns_bm25_contract` fail với `IndexError: list index out of range` vì output rỗng. Lọc theo overlap diễn đạt đúng ý định ("bỏ chunk không dính từ nào") và không phụ thuộc kích thước corpus; score âm (idf bị floor bằng epsilon) vẫn bị bỏ.
   **Trade-off:** Phải giữ thêm token set của từng chunk trong cache (tốn RAM ~ kích thước corpus) và chunk chỉ trùng một từ phổ biến vẫn lọt vào danh sách với điểm rất thấp. Chấp nhận được vì `top_k` cắt phía sau, và Task 9 quyết fallback bằng dense score chứ không bằng BM25.

2. **Quyết định:** Tokenizer tiếng Việt = `\w+` theo Unicode (giữ dấu thanh) **cộng thêm** một pattern giữ nguyên mã văn bản dạng `81/2021/nđ-cp` thành một token.
   **Lý do/evidence:** `.lower().split()` để nguyên dấu câu nên `"NĐ-CP."` và `"NĐ-CP"` thành hai token khác nhau. Ngược lại nếu chỉ `\w+` thì `81/2021/NĐ-CP` vỡ thành `81, 2021, nđ, cp` — trùng gần hết với `97/2023/NĐ-CP`. Đo trên corpus 3 văn bản: query `"81/2021/NĐ-CP"` cho chunk đúng **1.636** điểm so với **0.132** của nghị định anh em — chênh ~12 lần, đúng chỗ dense embedding hay nhầm vì hai câu gần như đồng nghĩa.
   **Trade-off:** Không làm word segmentation nên từ ghép ("học phí") vẫn là hai token rời, BM25 mất một phần khả năng phân biệt cụm từ. Chấp nhận vì phần ngữ nghĩa đã có dense lo, và thêm underthesea/pyvi sẽ kéo theo dependency nặng cho cả nhóm.

## Kiểm thử và kết quả

- **Contract tests:** `pytest tests/test_contracts.py -k "signatures or semantic or lexical or rrf" -q` → **4 passed**. Các test còn fail trong suite thuộc Task 8/9 (Evaluation), Task 10 (Generation) và dữ liệu chuẩn hoá (Data), không thuộc phần tôi.
- **Dense trên ChromaDB thật** (không dùng fake collection): index 3 chunk với vector tự đặt, `semantic_search` trả đúng `1.0000 / 0.8000 / 0.0000` cho vector trùng khớp / cosine-sim 0.8 / trực giao → xác nhận `score = 1 - cosine_distance` và không có normalize thừa, đúng con số Task 9 dùng để so `SCORE_THRESHOLD`.
- **BM25 trên corpus tiếng Việt thật** (8 tài liệu thư viện → 32 chunk): `"dịch vụ quét trùng lặp luận văn"` → đúng 2 chunk của `dich-vu-quet-trung-lap.md` ở top (16.169 / 16.037), bỏ xa chunk thứ ba (4.258). Query `"thời gian mở cửa phòng đọc thư viện"` → chunk nội quy phòng đọc đứng đầu.
- **RRF trên kết quả thật:** fuse 1 list dense + 1 list BM25, chunk xuất hiện ở **cả hai** list (rank 3 dense + rank 5 BM25) được đẩy lên hạng 1 với `0.031258 = 1/63 + 1/65`, vượt cả hai chunk đang đứng rank 1 của từng list (`0.016393 = 1/61`) → đúng tính chất thưởng đồng thuận của RRF.
- **Edge case:** query rỗng, `top_k=0`, `ranked_lists` toàn list rỗng, fuse một list duy nhất — tất cả trả `[]` hoặc kết quả hợp lệ, không raise.
- **Lỗi đã phát hiện và cách xử lý:**
  - `test_lexical_search_returns_bm25_contract` fail do idf = 0 trên corpus nhỏ → đổi tiêu chí lọc sang token overlap (xem quyết định 1).
  - `.venv` trong repo là Python 3.14 trong khi `pyproject.toml` yêu cầu `>=3.10,<3.14`, và chưa cài dependency nào → dựng lại venv bằng Python 3.13 rồi mới chạy được test.
  - RRF ban đầu ghi đè `score`/`retrieval_method` ngay trên dict gốc của dense/BM25 → sửa thành copy cả dict lẫn `metadata`, vì Task 9 còn đọc `dense[0]["score"]` (cosine gốc) sau khi đã fuse; nếu mutate thì fallback sẽ so threshold với RRF score (~0.03) và fallback ở mọi query.

## Điều còn hạn chế

- **Hạn chế cụ thể:** Chưa chạy được A/B dense-vs-BM25 head-to-head trên corpus thật, vì `data/standardized/` còn rỗng và `chroma_db/` chưa được build (Task 1–3 chưa chạy ra dữ liệu, Task 4 mới có code). Bằng chứng "BM25 thắng dense ở query từ khoá" hiện dựa trên corpus 3 văn bản tự dựng, chưa phải corpus nộp bài. Ngoài ra tokenizer không tách từ ghép tiếng Việt.
- **Nếu có thêm thời gian:** chạy `task3` + `task4` để có index thật, rồi đo bảng so sánh rank của dense và BM25 trên đúng 15 câu golden dataset — đặc biệt 3 câu cần khớp từ khoá chính xác — và nộp con số đó cho phần A/B trong `RESULT.md` thay cho ví dụ tự dựng.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 20/09/2026
- Tên thành viên: Nguyễn Đăng Thực
