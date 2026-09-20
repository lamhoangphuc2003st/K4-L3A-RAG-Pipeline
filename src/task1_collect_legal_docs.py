"""
Task 1 — Thu thập tài liệu chính sách/quy định.

Đề tài nhóm: dịch vụ đại học — học phí, học bổng, ký túc xá, thư viện,
đăng ký học phần.

Mọi tài liệu trong ``SOURCES`` đều tải trực tiếp từ website công khai của
cơ quan/nhà trường, không qua tường đăng nhập và không vượt WAF. Chạy lại
script sẽ bỏ qua file đã tải hợp lệ nên không tốn băng thông.
"""

from pathlib import Path

import requests


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

# Số tài liệu tối thiểu theo yêu cầu của đề (tests/test_acceptance.py).
MIN_DOCUMENTS = 3

# Kích thước tối thiểu để coi là file thật, khớp ngưỡng của acceptance test.
MIN_FILE_SIZE = 1024

REQUEST_TIMEOUT = 90
USER_AGENT = "Mozilla/5.0 (compatible; K4-L3A-RAG-Pipeline/0.1)"

# Tên file không dấu, thể hiện đúng nội dung tài liệu.
SOURCES: dict[str, str] = {
    # Học phí — văn bản hợp nhất Nghị định về cơ chế thu, quản lý học phí.
    "nghidinh-hop-nhat-co-che-thu-hoc-phi.pdf": (
        "https://quantrisgd.shieldix.app/data/doc/2024/hanoi/phapche/2024_6/13/"
        "van-ban-hop-nhat-nd-quy-dinh-co-che-thu-quan-ly-hoc-phi_136202416.pdf"
    ),
    # Học phí + thư viện + đăng ký học phần — sổ tay sinh viên Học viện Nông nghiệp VN.
    "sotay-sinhvien-vnua-k69.pdf": (
        "https://file.vnua.edu.vn/data/0/documents/2025/06/17/host/"
        "sotaysinhvien-k69.pdf"
    ),
    # Học bổng — quy định quản lý và sử dụng học bổng, ĐH Công nghệ (VNU-UET).
    "quy-dinh-quan-ly-su-dung-hoc-bong-uet.pdf": (
        "https://uet-test.uet.edu.vn/wp-content/uploads/2025/10/"
        "Dieu-3_Quy-dinh-ve-quan-ly-va-su-dung-hoc-bong-1.pdf"
    ),
    # Học bổng — quy định xét cấp học bổng, ĐH Quốc tế (HCMIU).
    "quy-dinh-xet-cap-hoc-bong-hcmiu.pdf": (
        "https://edusoftweb.hcmiu.edu.vn/Upload/"
        "Quy%20%C4%91%E1%BB%8Bnh%20x%C3%A9t%20c%E1%BA%A5p%20h%E1%BB%8Dc%20b%E1%BB%95ng"
        "%20t%E1%BA%A1i%20Tr%C6%B0%E1%BB%9Dng%20%C4%90HQT%20-%20Signed%20(4).pdf"
    ),
    # Ký túc xá — nội quy công tác nội trú, ĐH Cần Thơ.
    "noi-quy-ktx-ctu.pdf": (
        "https://dsa.ctu.edu.vn/images/upload/vbanply/KTX%20sinh%20vien/"
        "Noi%20quy%20KTX%20nam%202016.pdf"
    ),
    # Ký túc xá — quy định quản lý khu KTX và sinh viên nội trú, VNUA.
    "quy-dinh-quan-ly-ktx-sinh-vien-noi-tru-vnua.pdf": (
        "https://file.vnua.edu.vn/DATA/0/DOCUMENTS/2016/06/host/"
        "22.Quy_dinh_ve_quan_ly_khu_ki_tuc_xa_va_sinh_vien_noi_tru.pdf"
    ),
    # Ký túc xá — quy chế công tác sinh viên nội trú, ĐH Y Hà Nội.
    "quy-che-sinh-vien-noi-tru-hmu.pdf": (
        "https://apiwebhmu.hmu.edu.vn/Upload/Images/"
        "46eaf90a-146f-4ed6-b48c-19bc20c06a1f.pdf"
    ),
}


def setup_directory() -> None:
    """Tạo thư mục lưu tài liệu gốc."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def is_valid_pdf(path: Path) -> bool:
    """Kiểm tra file tồn tại, đủ lớn và đúng magic bytes của PDF."""
    if not path.is_file() or path.stat().st_size <= MIN_FILE_SIZE:
        return False
    with path.open("rb") as handle:
        return handle.read(4) == b"%PDF"


def download_documents() -> None:
    """Tải tài liệu chính sách trong ``SOURCES`` vào ``data/landing/legal``.

    Bỏ qua file đã tải hợp lệ. File trả về HTML (bị chặn) hoặc quá nhỏ sẽ bị
    xoá để không lọt vào bước chuẩn hoá. Raise khi số tài liệu hợp lệ không
    đạt ``MIN_DOCUMENTS``.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for filename, url in SOURCES.items():
        target = DATA_DIR / filename

        if is_valid_pdf(target):
            print(f"Skip (da co): {filename}")
            continue

        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            target.write_bytes(response.content)
        except requests.RequestException as error:
            print(f"Failed: {filename} — {error}")
            target.unlink(missing_ok=True)
            continue

        if not is_valid_pdf(target):
            # Nguồn trả về trang chặn hoặc file rỗng thay vì PDF.
            print(f"Rejected (khong phai PDF): {filename}")
            target.unlink(missing_ok=True)
            continue

        print(f"Saved: {filename} ({target.stat().st_size} bytes)")

    valid = [path for path in sorted(DATA_DIR.glob("*.pdf")) if is_valid_pdf(path)]
    print(f"Valid legal documents: {len(valid)}/{MIN_DOCUMENTS} required")
    if len(valid) < MIN_DOCUMENTS:
        raise RuntimeError(
            f"Chi co {len(valid)} tai lieu hop le, can toi thieu {MIN_DOCUMENTS}. "
            "Bo sung nguon cong khai khac vao SOURCES."
        )


if __name__ == "__main__":
    setup_directory()
    download_documents()
