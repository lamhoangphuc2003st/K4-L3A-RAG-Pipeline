# Thành viên nhóm

- **Lớp:** K4 — L3A
- **Repository:** `K4-L3A-RAG-Pipeline`
- **Nhánh làm việc của nhóm:** `dev` (mọi nhánh cá nhân merge vào `dev`, cuối buổi PR `dev` → `main`)
- **Đề tài:** Dịch vụ đại học — học phí, học bổng, ký túc xá, thư viện, đăng ký học phần

| # | Họ và tên | Mã học viên | Vai trò | Nhánh | Phần việc |
|--:|-----------|-------------|---------|-------|-----------|
| 1 | Nguyễn Văn Tài | 2A202603004 | **Data** | `feat/data` | Task 1 thu thập tài liệu chính sách, Task 2 crawl bài viết, Task 3 chuẩn hoá Markdown, Task 4 chunking + embedding + index ChromaDB |
| 2 | Nguyễn Đăng Thực | 2A202603014 | **Retrieval** | `feat/retrieval` | Task 5 dense search, Task 6 BM25, Task 7 Reciprocal Rank Fusion |
| 3 | Nguyễn Đức Minh | 2A202602891 | **Generation/UI** | `feat/generation-ui` | Task 10 generation có citation + safe refusal, chatbot Streamlit `app.py` |
| 4 | Lâm Hoàng Phúc | 2A202602582 | **Evaluation/Integration** | `feat/evaluation` | Task 8 PageIndex fallback, Task 9 retrieval pipeline + hiệu chỉnh threshold, golden dataset 15+ câu, 4 metric RAGAS, A/B, `RESULT.md`, giữ `pytest` xanh |

Chi tiết nhiệm vụ, lịch chạy song song và các điểm đồng bộ: [`group_project/WORK_DIVISION.md`](group_project/WORK_DIVISION.md).

> Nếu nhóm chỉ có 3 người: gộp **Evaluation/Integration** vào **Data** (người này xong Task 1–4 sớm nhất), giữ nguyên 3 nhánh còn lại.

## Báo cáo cá nhân

Mỗi thành viên copy `group_project/ịndividual/INDIVIDUAL_REPORT.md` thành `reports/<mã-học-viên>-<tên-ngắn>.md` và tự điền.

| Thành viên | File báo cáo cá nhân |
|---|---|
| Nguyễn Văn Tài | `reports/2A202603004-tai.md` |
| Nguyễn Đăng Thực | `reports/2A202603014-thuc.md` |
| Nguyễn Đức Minh | `reports/2A202602891-minh.md` |
| Lâm Hoàng Phúc | `reports/2A202602582-phuc.md` |
