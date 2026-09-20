# RAG evaluation results

## Run information

| Field                              | Value |
| ---------------------------------- | ----- |
| Evaluation date                    | 2026-09-20 |
| Framework and version              | RAGAS 0.4.3 |
| Evaluator model                    | `gpt-4o-mini` (temperature 0), embeddings `text-embedding-3-small` |
| Generator model                    | `gpt-4o-mini` (temperature 0.3, top_p 0.9) |
| Embedding model                    | `BAAI/bge-m3`, 1024 chiều, chạy local qua `sentence-transformers` |
| Corpus version/commit              | 1300 chunk từ 7 tài liệu chính sách + 9 bài viết; chunk 500 ký tự, overlap 50 |
| Golden dataset size                | 22 câu — 17 in-domain, 3 keyword, 2 out-of-domain |
| `top_k`                            | 5 |
| Fallback threshold and calibration | **0.618**. Hiệu chỉnh bằng `calibrate_threshold()` trên 6 query in-domain (best dense score 0.677–0.713) và 2 query out-of-domain (0.476–0.559). Hai cụm tách rời, ngưỡng đặt ở giữa. |

## Configurations

- **Config A — dense-only:** `retrieve(query, top_k=5, use_reranking=False)` — chỉ lấy `semantic_search` rồi cắt top-5.
- **Config B — hybrid + RRF:** `retrieve(query, top_k=5, use_reranking=True)` — `semantic_search` và `lexical_search` mỗi bên lấy 10 ứng viên, hợp nhất bằng RRF (`k=60`) rồi cắt top-5.

Hai config dùng cùng golden dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy. Script ép `use_reranking` bằng cách tạm thay `task10_generation.retrieve` nên đường sinh câu trả lời hoàn toàn giống nhau.

## Overall scores

| Metric            | Config A | Config B | Delta B−A |
| ----------------- | -------: | -------: | --------: |
| Faithfulness      |    0.837 |    0.864 |    +0.027 |
| Answer relevance  |    0.471 |    0.449 |    −0.022 |
| Context recall    |    0.735 |    0.886 |    +0.152 |
| Context precision |    0.740 |    0.797 |    +0.058 |
| **Average**       |    0.696 |    0.749 |    +0.053 |

## A/B comparison

- **Cấu hình tốt hơn:** Config B (hybrid + RRF), trung bình 0.749 so với 0.696.

- **Evidence:** Mức tăng tập trung ở **context recall (+0.152)** — đúng chỗ kỳ vọng, vì BM25 kéo lên những chunk chứa từ khoá chính xác mà dense bỏ sót. Ví dụ cụ thể nhất là câu `gd-13` *"Sinh viên nội trú rời khỏi ký túc xá bao nhiêu ngày thì phải báo cáo, và báo cho ai?"*:

  - Config A lấy 5 chunk nhưng không có chunk chứa điều khoản "05 ngày" → mô hình trả lời *"Tôi không thể xác minh thông tin này từ nguồn hiện có."* Cả faithfulness và context recall đều 0.
  - Config B có BM25 khớp cụm "05 ngày", RRF đẩy chunk đó vào top-5 → trả lời đúng "dưới 05 ngày báo Phòng trưởng, từ 05 ngày trở lên Phòng trưởng báo Giám thị". Câu này rời khỏi nhóm 3 câu tệ nhất.

  Context precision cũng tăng (+0.058): RRF ưu tiên chunk được **cả hai** retriever đồng thuận, nên ít chunk nhiễu lọt vào context hơn.

- **Trade-off về latency/cost:** Config B chạy thêm một lượt BM25 trên 1300 chunk và lấy gấp đôi ứng viên (10 thay vì 5) trước khi fuse. BM25 chạy in-memory, không gọi API và không thêm chi phí token vì `top_k` cuối vẫn là 5 — chi phí LLM của hai config bằng nhau. Chi phí thật là bộ nhớ: `lexical_search` nạp toàn bộ corpus chunk vào RAM lần gọi đầu. Đổi lại được +0.152 context recall, rất đáng.

## Worst performers

|   # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage             | Root cause |
| --: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------------------- | ---------- |
|   1 | Tỷ giá đồng đô la Mỹ hôm nay là bao nhiêu? | A và B | 0.000 | 0.000 | 0.000 | 0.000 | evaluation | Câu ngoài domain. Hệ thống **hành xử đúng** — từ chối an toàn, không bịa. Nhưng RAGAS so answer với reference nên chấm 0 toàn bộ. Đây là hạn chế của cách đo, không phải lỗi pipeline. |
|   2 | Trường có bán vé máy bay giá rẻ cho sinh viên đi du lịch nước ngoài không? | A và B | 0.000 | 0.000 | 0.500 | 0.000 | evaluation | Tương tự câu 1. Recall 0.5 vì một chunk về dịch vụ sinh viên tình cờ khớp một phần reference. |
|   3 | Sinh viên nội trú rời khỏi ký túc xá bao nhiêu ngày thì phải báo cáo, và báo cho ai? | A | 0.000 | 0.000 | 0.000 | 0.325 | retrieval | Dense không lấy được chunk chứa "05 ngày" vì câu hỏi diễn đạt khác văn bản gốc. **Config B đã sửa được** nhờ BM25. |
|   4 | Quy định về quản lý khu ký túc xá và sinh viên nội trú được ban hành kèm theo quyết định số nào? | B | 0.667 | 0.581 | 1.000 | 0.250 | retrieval | Recall 1.0 nhưng precision chỉ 0.25: chunk chứa số `02/QĐ-NNH` lọt vào nhưng 3 chunk còn lại là điều khoản KTX không liên quan. Chunk 500 ký tự cắt phần căn cứ pháp lý ra khỏi phần tiêu đề. |

**Quan sát quan trọng:** hai câu tệ nhất ở cả hai config đều là câu out-of-domain và đều đạt 0 dù hệ thống trả lời đúng cách. Hai câu này kéo mọi metric xuống ở cả A lẫn B như nhau, nên **không ảnh hưởng tới kết luận so sánh**, nhưng khiến điểm tuyệt đối thấp hơn năng lực thật của hệ thống.

Điều này cũng giải thích vì sao **answer relevance thấp bất thường (0.45–0.47)** ở cả hai config. RAGAS đo relevance bằng cách sinh câu hỏi ngược từ answer rồi so với câu hỏi gốc; safe refusal không sinh được câu hỏi ngược nào hợp lý nên bị 0. Ngoài ra prompt hiện tại yêu cầu trả lời ngắn gọn, câu trả lời một dòng kèm `[Document 1]` cũng làm giảm điểm relevance.

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
|        1 | Tách riêng chỉ số cho câu out-of-domain: đo bằng tỷ lệ từ chối đúng thay vì 4 metric của RAGAS | 2/22 câu đạt 0 toàn bộ dù hành xử đúng, kéo cả 4 metric xuống | Điểm in-domain phản ánh đúng năng lực; refusal được chấm bằng thước đo phù hợp | Chạy lại evaluation tách hai nhóm, so điểm in-domain trước/sau |
|        2 | Tăng chunk size lên 800–1000 với overlap 150, hoặc chunk theo Điều/Khoản | Câu 4: recall 1.0 nhưng precision 0.25 — chunk 500 ký tự cắt rời số hiệu văn bản khỏi nội dung điều khoản | Context precision tăng, giảm chunk nhiễu trong top-5 | Index lại rồi chạy đúng golden dataset này, so context precision |
|        3 | Nới prompt cho phép trả lời đầy đủ 2–3 câu thay vì một dòng | Answer relevance 0.45–0.47 trong khi faithfulness 0.86 — trả lời đúng nhưng quá ngắn để RAGAS sinh lại câu hỏi | Answer relevance tăng mà không ảnh hưởng faithfulness | Chạy lại Config B với prompt mới, so answer relevance và faithfulness |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| ---------- | -------- | -----------: | -----------------: | ---------- |
| Không thực hiện | — | — | — | Nhóm ưu tiên hoàn thiện pipeline chính và phân tích lỗi; chưa chạy HyDE, reranker nâng cao hay conversation memory. |
