# Individual contribution report

> **Khung nháp — cần tự kiểm tra trước khi nộp.**
> Phần dữ kiện (file, commit, kết quả test) đã đối chiếu với repo tại commit `1462784`.
> Chỗ đánh dấu `【…】` phải tự điền hoặc xác nhận lại sau khi chạy evaluation thật.
> Xoá toàn bộ khối trích dẫn này trước khi nộp.

## Thông tin

- Họ và tên: Lâm Hoàng Phúc
- Mã học viên: 2A202602582
- Nhóm: K4 — L3A
- Repository/branch: https://github.com/lamhoangphuc2003st/K4-L3A-RAG-Pipeline — nhánh `dev`
- Vai trò: Evaluation/Integration

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Task 9 — Retrieval pipeline | `retrieve()` gộp dense + BM25 bằng RRF đúng một lần, quyết định fallback theo cosine score gốc, nuốt lỗi PageIndex để không sập UI | `src/task9_retrieval_pipeline.py` — commit `1462784` | Done |
| Task 9 — Hiệu chỉnh threshold | `calibrate_threshold()` in best dense score của nhóm in-domain và out-of-domain, cảnh báo khi hai cụm chồng nhau | `src/task9_retrieval_pipeline.py` — commit `1462784` | 【Partial — đã viết hàm, chưa chạy được vì Task 5 chưa hoàn thành】 |
| Task 8 — PageIndex fallback | Client có timeout, cache document ID ra file, convert Markdown sang PDF, parse retrieved node thành `SearchResult`; thiếu API key thì trả `[]` thay vì ném lỗi | `src/task8_pageindex_vectorless.py` — commit `1462784` | 【Partial — nhóm chưa có `PAGEINDEX_API_KEY` nên chưa verify response thật】 |
| Golden dataset | Viết 22 câu Q&A bám trích dẫn thật của 6/7 tài liệu: 17 in-domain, 3 keyword, 2 out-of-domain | `group_project/evaluation/golden_dataset.json` — commit `1462784` | Done |
| Evaluation harness | Script A/B chạy 4 metric RAGAS cho dense-only và hybrid+RRF, xuất `evaluation_raw.json` và bảng so sánh | `group_project/evaluation/run_evaluation.py` — commit `1462784` | 【Partial — chưa chạy được vì Task 5/6/7 và Task 10 chưa xong】 |
| Tổ chức nhóm | `TEAMMATES.md`, phân công 10 task theo 4 role, lịch song song và 3 mốc đồng bộ | `TEAMMATES.md`, `group_project/WORK_DIVISION.md` — commit `c85a952` | Done |
| Vệ sinh repo | Thêm `chroma_db/` vào `.gitignore` (template thiếu, Task 4 sinh vector DB nhị phân ngay trong repo) | `.gitignore` — commit `c85a952` | Done |
| `RESULT.md` | 【Chưa làm — chờ pipeline chạy end-to-end】 | `group_project/evaluation/RESULT.md` | Blocked |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Fallback so sánh threshold với cosine score gốc của dense retrieval (`dense[0]["score"]`), không dùng RRF score.
   **Lý do/evidence:** Hai đại lượng khác thang đo. Cosine similarity nằm trong `[0, 1]`, còn RRF score với `k=60` chỉ quanh `1/61 ≈ 0.016` kể cả khi chunk khớp hoàn hảo. Nếu so RRF score với ngưỡng 0.3 thì **mọi** query đều rơi vào fallback, kể cả query in-domain. Contract test `test_retrieve_uses_dense_score_for_fallback` kiểm tra đúng hành vi này.
   **Trade-off:** Quyết định fallback chỉ nhìn tín hiệu dense, nên query mà BM25 khớp rất mạnh còn dense yếu (ví dụ hỏi đúng số hiệu `02/QĐ-NNH`) vẫn bị coi là "không tự tin" và gọi fallback không cần thiết. Chấp nhận vì fallback lỗi đã có nhánh trả về hybrid, chi phí sai là một lần gọi API thừa chứ không mất kết quả.

2. **Quyết định:** Task 8 trả về danh sách rỗng khi thiếu `PAGEINDEX_API_KEY` hoặc SDK lỗi, thay vì ném exception cho Task 9 bắt.
   **Lý do/evidence:** Nhóm không có API key PageIndex, nên "không có fallback" là trạng thái vận hành bình thường chứ không phải lỗi. Đề yêu cầu provider lỗi không được làm UI crash; Task 9 vẫn giữ `try/except` để phòng lỗi thật (timeout, đổi schema), nhưng không nên dùng exception cho luồng bình thường. Contract test `test_retrieve_survives_fallback_provider_error` xác nhận nhánh exception vẫn hoạt động.
   **Trade-off:** Lỗi cấu hình sai (ví dụ gõ nhầm key) sẽ im lặng trở thành "không có fallback" thay vì báo lỗi rõ. Bù lại bằng log cảnh báo và cờ `--probe` để kiểm tra response thật khi có key.

## Kiểm thử và kết quả

- Lệnh đã chạy: `pytest tests/test_contracts.py -q` và `pytest tests/test_acceptance.py -q`
- Kết quả contract test cho phần của tôi: **4/4 pass** — `test_public_function_signatures_are_stable`, `test_retrieve_uses_dense_score_for_fallback`, `test_retrieve_fuses_once_when_dense_is_confident`, `test_retrieve_survives_fallback_provider_error`
- Acceptance test: `test_golden_dataset_has_15_grounded_cases` chuyển từ đỏ sang xanh (22 case, trước đó file rỗng khiến `json.loads` crash)
- Lỗi đã phát hiện và xử lý:
  - `golden_dataset.json` trong template là **file rỗng**, không phải file thiếu nội dung — `json.loads` ném `JSONDecodeError` làm acceptance test đỏ trước khi kiểm tra được số lượng case.
  - `.gitignore` thiếu `chroma_db/`, vector DB nhị phân sẽ bị commit vào repo sau khi chạy Task 4.
  - Bộ dữ liệu thư viện UTH đẩy lên ban đầu nằm ngoài `data/landing/`, không được acceptance test đếm; nhóm đã chốt bỏ và dùng 7 PDF về học phí/ký túc xá/học bổng.
- 【Chưa chạy được: `calibrate_threshold()`, `run_evaluation.py` và demo A/B — phụ thuộc Task 5/6/7 và Task 10】

## Điều còn hạn chế

- Hạn chế cụ thể: Threshold fallback hiện vẫn là giá trị mặc định `0.3` chưa hiệu chỉnh trên corpus thật. Hàm `calibrate_threshold()` đã sẵn sàng nhưng cần Task 5 hoạt động mới chạy được, nên con số này chưa có cơ sở thực nghiệm.
- Nếu có thêm thời gian: 【Đề xuất — tự xác nhận】 chạy `calibrate_threshold()` trên 5 câu in-domain và 2 câu out-of-domain trong golden dataset, chốt ngưỡng theo số đo và ghi bằng chứng vào `RESULT.md`; sau đó bổ sung câu hỏi cho tài liệu `quy-che-sinh-vien-noi-tru-hmu.md` — hiện là tài liệu duy nhất chưa có golden case nào.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 【điền ngày nộp】
- Tên thành viên: Lâm Hoàng Phúc
