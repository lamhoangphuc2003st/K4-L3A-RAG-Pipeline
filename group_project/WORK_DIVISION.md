# Phân công công việc — 4 role

Bốn role theo gợi ý của đề: **Data**, **Retrieval**, **Generation/UI**, **Evaluation/Integration**.
Tên và mã học viên của từng người: xem [`TEAMMATES.md`](../TEAMMATES.md) ở root.

Mọi mốc thời gian tính từ lúc bắt đầu buổi lab (T+0), theo lộ trình 3 giờ trong README.

## 0. Chốt trước khi code (10 phút đầu, cả nhóm cùng làm)

| Việc           | Quyết định                                                                                                              |
| -------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Đề tài         | **Dịch vụ đại học** (học phí, học bổng, ký túc xá, thư viện, đăng ký học phần) — `src/__init__.py` đã ghi sẵn chủ đề này |
| Embedding      | `sentence_transformers` + `BAAI/bge-m3` (1024 dim), chạy local, không tốn quota                                          |
| LLM generation | 1 provider duy nhất cho cả nhóm (`LLM_PROVIDER` trong `.env`) để A/B evaluation công bằng                               |
| Vector DB      | ChromaDB persistent, cosine, collection `rag_documents`                                                                  |
| Nhánh nhóm     | `dev`; mỗi role làm trên nhánh riêng rồi merge vào `dev`, cuối buổi PR `dev` → `main`                                    |

Mỗi người tự tạo `.env` từ `.env.example`. **Không commit `.env` hay API key.**

---

## 1. Bảng phân công

| Role                        | Nhánh                | Task sở hữu                          | File được sửa                                                     | Điểm rubric gánh |
| --------------------------- | -------------------- | ------------------------------------ | ------------------------------------------------------------------ | ---------------: |
| **Data**                    | `feat/data`          | Task 1, 2, 3, 4                      | `src/task1_*`, `task2_*`, `task3_*`, `task4_*`, `data/`           |              20 |
| **Retrieval**               | `feat/retrieval`     | Task 5, 6, 7                         | `src/task5_*`, `task6_*`, `task7_*`                               |              20 |
| **Generation/UI**           | `feat/generation-ui` | Task 10 + chatbot                    | `src/task10_*`, `app.py`                                          |              25 |
| **Evaluation/Integration**  | `feat/evaluation`    | Task 8, 9 + đánh giá + tích hợp      | `src/task8_*`, `task9_*`, `group_project/evaluation/`, `README.md` |              25 |

**File cấm sửa:** `src/contracts.py`, `tests/test_contracts.py`, `tests/test_acceptance.py`, `docs/*`. Đây là contract của đề; sửa = mất điểm.

**Không đổi tên tham số hàm.** `tests/test_contracts.py::test_public_function_signatures_are_stable` so khớp đúng tên và thứ tự tham số của cả 8 hàm public.

---

## 2. Chi tiết từng role

### Role 1 — Data (Task 1, 2, 3, 4)

Sở hữu toàn bộ đường đi từ nguồn gốc đến vector store. Đây là role chặn cả nhóm nên đẩy dữ liệu ra sớm nhất có thể.

**T+10 → T+35 — thu thập**

- Task 1: tải ≥3 PDF/DOCX chính sách vào `data/landing/legal/`. Mỗi file **>1KB** (acceptance test kiểm tra `st_size > 1024`). Tên file không dấu.
- Task 2: điền ≥5 URL vào `ARTICLE_URLS`, crawl ra JSON trong `data/landing/news/`. Mỗi JSON **bắt buộc** đủ 4 key: `url`, `title`, `date_crawled`, `content_markdown` — không key nào được rỗng.
- Task 3: convert sang `data/standardized/legal/*.md` và `standardized/news/*.md`. Mỗi file **≥200 ký tự** sau khi strip. Chạy lại không được tạo file trùng.
- **Ưu tiên tuyệt đối:** trong ~10 phút đầu đẩy trước **1 PDF + 1 JSON** lên `dev` để 3 role kia có dữ liệu chạy thử. Đừng chờ đủ 8 file mới push.

**T+35 → T+70 — chunk, embed, index (Task 4)**

- `embed_texts()`: dispatch theo `EMBEDDING_PROVIDER`. Task 5 sẽ import lại **đúng hàm này** — không để tồn tại model thứ hai trong repo.
- `get_collection()`: persistent client, `metadata={"hnsw:space": "cosine"}`.
- `chunk_documents()`: id chunk phải **ổn định** (vd `legal/hocphi.md::chunk-3`) để `upsert` chạy lại không nhân đôi dữ liệu. Mỗi chunk có `metadata.chunk_index` là int ≥ 0, content không rỗng.
- Chroma **không nhận metadata value là `None`** → `url: None` của doc legal sẽ lỗi khi upsert. Ép thành `""` trước khi ghi, hoặc bỏ key.
- Tải model bge-m3 (~2GB) **ngay phút đầu tiên**, song song lúc đang đi tìm tài liệu.
- Bàn giao cho Retrieval: một hàm nạp được đúng bộ chunks (`chunk_documents(load_documents())`) để BM25 dùng chung corpus với dense.

### Role 2 — Retrieval (Task 5, 6, 7)

**T+10 → T+30 — Task 7 RRF (làm được ngay, không cần dữ liệu)**

- Hàm thuần: `RRF(d) = Σ 1/(k + rank)`, **rank bắt đầu từ 1**.
- Output `retrieval_method="hybrid"`, score = RRF score, sort giảm dần, cắt `top_k`.
- Tự test với 2 ranked list giả trước khi có corpus thật.

**T+70 → T+95 — Task 5 dense**

- Import `embed_texts` và `get_collection` từ Task 4, không tự tạo model mới.
- Cosine **distance** của Chroma → similarity: `score = max(0.0, 1.0 - distance)`. Task 9 dùng chính con số này để quyết fallback nên **đừng normalize thêm**.
- Không trùng ID, không vượt `top_k`, sort giảm dần, `retrieval_method="dense"`.

**T+95 → T+2:00 — Task 6 BM25**

- `CORPUS` hiện là list rỗng, không có hàm nạp sẵn. Nạp bằng **đúng bộ chunks của Task 4**. Nếu BM25 chạy trên corpus khác dense, RRF sẽ fuse nhầm ID → mất phần lớn 20 điểm của mục "Dense search, BM25 và RRF".
- Tiếng Việt: `.lower().split()` là tối thiểu; cân nhắc bỏ dấu câu. Ghi lựa chọn vào individual report.
- Bỏ kết quả score ≤ 0, `retrieval_method="bm25"`.
- Đảm bảo có ít nhất 1 query keyword (mã văn bản, số tiền) mà BM25 thắng dense — đây là evidence cho phần A/B.

### Role 3 — Generation/UI (Task 10 + `app.py`)

**T+10 → T+40 — phần không cần retrieval**

- `reorder_for_llm()`: chống lost-in-the-middle, chunk quan trọng nhất ở đầu và cuối. Reorder **không được làm mất hoặc đổi ID** — `sources` trả về phải map được với citation.
- `format_context()`: mỗi block có `Document i`, `Title`, `Source` để citation kiểm chứng được.
- `app.py`: dựng khung UI + chỗ hiển thị sources, tạm gọi một hàm generate giả trả dữ liệu cứng.

**T+40 → T+1:45 — generation thật**

- `call_llm()`: dispatch 3 nhánh openai / gemini / anthropic theo `LLM_PROVIDER`, dùng `LLM_MODEL`, cả 3 nhánh trả **text thuần**. Không hard-code key.
- `generate_with_citation()`: trả đúng `GenerationResult` — `answer`, `sources` (list SearchResult hợp lệ), `retrieval_source` ∈ `hybrid|pageindex|none`.
- Retrieve rỗng → safe refusal + `sources: []` + `retrieval_source: "none"`. Đây là 1 trong 3 query bắt buộc demo.
- Provider lỗi (hết quota, timeout) → cũng trả safe refusal, không để traceback nổi lên Streamlit.

**T+1:45 → T+2:10 — hoàn thiện chatbot**

- Hiển thị: answer, danh sách source (title + source + score), `retrieval_method`.
- Lưu cả answer lẫn sources vào `st.session_state` để lịch sử chat render lại được nguồn.
- Slider `top_k` ở sidebar phải thực sự truyền vào `generate_with_citation`.

### Role 4 — Evaluation/Integration (Task 8, 9 + đánh giá)

Vừa ghép các mảnh của 3 role kia thành pipeline chạy được, vừa đo chất lượng.

**T+10 → T+55 — golden dataset (không cần chờ ai)**

- Viết ≥15 câu vào `group_project/evaluation/golden_dataset.json`. File này hiện **rỗng hoàn toàn** → `json.loads` sẽ crash acceptance test, bắt buộc phải điền.
- Schema mỗi case: `{"question": ..., "expected_answer": ..., "expected_context": ...}`, cả 3 field không rỗng.
- Trộn: ~10 câu in-domain, ~3 câu cần khớp từ khóa chính xác (mã văn bản, số tiền), ~2 câu out-of-domain.

**T+55 → T+1:20 — Task 8 PageIndex fallback**

- Đọc `PAGEINDEX_API_KEY`, upload tài liệu, **cache document ID** ra file để không upload lại mỗi lần chạy.
- Bọc timeout + try/except. Yêu cầu của đề: _provider lỗi không được làm UI crash_.
- Không xin được API key → cho `pageindex_search` trả `[]` sạch sẽ và ghi rõ hạn chế trong report; Task 9 đã có nhánh xử lý lỗi.

**T+1:20 → T+1:50 — Task 9 retrieval pipeline**

- Gọi `semantic_search` và `lexical_search` với `top_k*2`, fuse **đúng một lần** bằng RRF.
- Fallback so sánh threshold với **`dense[0]["score"]` (cosine gốc)**, tuyệt đối không dùng RRF score — RRF score luôn ~0.03 nên sẽ fallback ở mọi query.
- `use_reranking=False` → trả `dense[:top_k]`. Nhánh này chính là Config A của A/B, đừng làm hỏng.
- PageIndex lỗi → `except` → trả hybrid, không raise lên UI.
- **Hiệu chỉnh threshold:** lấy ~5 câu in-domain và 2 câu out-of-domain từ golden dataset, in best dense score của từng câu, chọn ngưỡng nằm giữa hai cụm. Ghi số liệu vào `.env` (`SCORE_THRESHOLD`) và vào RESULT.md. Không lấy đại 0.3.

**T+2:10 → T+2:45 — đánh giá và tích hợp**

- Chạy RAGAS 4 metric: faithfulness, answer relevance, context recall, context precision.
- A/B: Config A = `retrieve(..., use_reranking=False)` (dense-only), Config B = `use_reranking=True` (hybrid + RRF). **Chỉ đổi đúng một biến này**, giữ nguyên golden dataset / generator / evaluator / prompt / `top_k`.
- Điền `group_project/evaluation/RESULT.md` — acceptance test fail nếu còn bất kỳ chữ `TODO` nào.
- Giữ `pytest -q` xanh, review PR của 3 role kia, cập nhật `README.md` theo đề tài nhóm.

---

## 3. Lịch chạy song song

```
                0:00   0:35            1:10          1:45          2:10          2:45   3:00
Data          | setup | T1,T2,T3      | T4 index     | hỗ trợ debug | bổ sung data | report |
Retrieval     | setup | T7 (RRF)      | T5 (dense)   | T6 (BM25)    | tinh chỉnh   | report |
Generation/UI | setup | T10 format+UI | T10 call_llm | UI đầy đủ    | fix theo eval| report |
Eval/Integr.  | setup | golden 15 Q&A | T8 pageindex | T9 pipeline  | RAGAS + A/B  | RESULT.md |
```

**3 điểm đồng bộ bắt buộc — cả nhóm dừng 5 phút:**

| Mốc        | Kiểm tra                                                                                                                  |
| ---------- | --------------------------------------------------------------------------------------------------------------------------- |
| **T+70**   | Data demo `python -m src.task4_chunking_indexing` in ra số chunk > 0; chốt với Retrieval cách nạp `CORPUS` cho BM25.         |
| **T+1:50** | Retrieval giao đủ T5/T6/T7; Eval demo `retrieve()` trả kết quả thật; Generation cắm vào chạy end-to-end 1 câu.               |
| **T+2:10** | `pytest -q` xanh toàn bộ; đóng băng code retrieval, từ đây chỉ Eval chạy đo — không ai push thay đổi pipeline nữa.           |

---

## 4. Quy tắc Git

- Nhánh nhóm `dev`; nhánh cá nhân `feat/data`, `feat/retrieval`, `feat/generation-ui`, `feat/evaluation`.
- Merge vào `dev` qua PR, một người khác review 1 phút. Cuối buổi PR `dev` → `main`.
- Commit message có prefix task: `task4: implement chunk_documents with stable ids`.
- **Mỗi người ghi lại commit hash của mình ngay khi push** — individual report yêu cầu đối chiếu bằng file/commit/PR, cuối buổi mò lại rất mất thời gian.
- Commit nhỏ và thường xuyên, không dồn vào 1 commit cuối buổi (không chứng minh được ownership).
- Trước khi push: kiểm tra không có `.env`, `chroma_db/`, `__pycache__`, hay API key trong code.

## 5. Checklist nộp bài

- [ ] `TEAMMATES.md` ở root đã điền đủ họ tên, mã học viên, vai trò, nhánh của từng thành viên
- [ ] `pytest tests/test_contracts.py -q` xanh
- [ ] `pytest tests/test_acceptance.py -q` xanh (≥3 legal, ≥5 news, ≥15 golden case, `RESULT.md` không còn `TODO`)
- [ ] `streamlit run app.py` chạy được
- [ ] Demo 3 query: 1 câu đúng domain, 1 câu ngoài domain (safe refusal), 1 kết quả A/B
- [ ] **Mỗi người** copy `group_project/ịndividual/INDIVIDUAL_REPORT.md` thành `reports/<mã-học-viên>-<tên-ngắn>.md` và tự điền

## 6. Bonus (tối đa +10đ, chỉ tính khi chạy được và có số đo)

| Bonus                                    | Điểm | Giao cho                                  |
| ---------------------------------------- | ---: | ----------------------------------------- |
| HyDE / query expansion có A/B chứng minh |   +3 | Evaluation/Integration (sẵn hạ tầng đo)   |
| Reranker nâng cao (Jina/BGE) so với RRF  |   +3 | Retrieval                                 |
| Conversation memory cho follow-up        |   +2 | Generation/UI                             |
| Deploy online hoặc highlight citation    |   +2 | Generation/UI                             |

Chỉ làm bonus **sau khi** checklist mục 5 đã xanh hết.

## 7. Rủi ro đã biết

| Rủi ro                                 | Xử lý                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------ |
| bge-m3 tải ~2GB, lần đầu rất lâu       | Data tải model ngay phút đầu tiên, song song lúc chờ thu thập tài liệu        |
| Chroma từ chối metadata `None`         | Ép `url` thành `""` trước khi upsert                                          |
| Không có `PAGEINDEX_API_KEY`           | Task 9 đã có nhánh except → vẫn trả hybrid; ghi rõ hạn chế trong report        |
| Crawl4AI bị WAF chặn                   | Đổi nguồn công khai khác, **không vượt WAF** (đề cấm)                          |
| Hết quota LLM lúc chạy RAGAS           | Đo thử trên 5 câu để ước lượng, sau đó chạy đủ 15 câu một lần duy nhất         |
| BM25 và dense chạy trên 2 corpus khác  | Task 5 và Task 6 đều phải bắt nguồn từ `chunk_documents(load_documents())`     |
| Nhóm chỉ có 3 người                    | Gộp Evaluation/Integration vào Data; giữ nguyên 3 nhánh còn lại                |
