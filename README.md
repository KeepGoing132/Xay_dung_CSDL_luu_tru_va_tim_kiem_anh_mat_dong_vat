# Hệ CSDL lưu trữ và tìm kiếm ảnh mặt động vật

## 1. Trạng thái và mục đích

Đây là **bộ tài liệu thiết kế và hướng dẫn triển khai**, chưa phải ứng dụng đã được xây dựng. Chưa thu thập ảnh, chưa trích xuất vector, chưa chạy thực nghiệm. Các số liệu ví dụ không được đưa vào báo cáo như kết quả thật.

Mục tiêu: quản lý ít nhất 500 ảnh mặt động vật và đặc trưng trong CSDL; nhận ảnh mới, tính độ tương đồng, trả về đúng 5 ảnh theo điểm giảm dần. Truy vấn có thể thuộc loài đã có hoặc chưa có trong CSDL.

Đầu vào căn cứ: đề bài trong ảnh người dùng cung cấp trong cuộc trò chuyện. Những lựa chọn kỹ thuật dưới đây là phương án đề xuất để bắt đầu, không phải yêu cầu được giảng viên chỉ định.

## 2. Phương án triển khai mặc định

| Thành phần | Lựa chọn | Lý do |
| --- | --- | --- |
| Ngôn ngữ | Python | Thuận tiện xử lý ảnh và tính vector |
| CSDL | SQLite | Có bảng, khóa, quan hệ, giao dịch; demo cục bộ đơn giản |
| Giao diện | Streamlit | Phù hợp demo tải ảnh, bảng điểm và hình trung gian |
| Tiền xử lý | Pillow, NumPy | RGB, EXIF, crop, resize và mảng ảnh |
| Đặc trưng | HSV, HOG, LBP; scikit-image | Dễ giải thích và so sánh từng nhóm |
| Xếp hạng | Duyệt chính xác toàn bộ vector | Quy mô 500 ảnh chưa cần chỉ mục vector gần đúng |
| Test | pytest | Kiểm tra hành vi và dữ liệu |

Nếu môn học bắt buộc SQL Server/MySQL, thay lớp repository và DDL trước khi code; giữ nguyên quy tắc đặc trưng, kiểu trả về và tiêu chí kiểm tra. Không dùng DDL SQLite nguyên xi cho hệ quản trị khác.

## 3. Tài liệu và thứ tự đọc

| File | Mục đích |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Quy tắc dành cho AI làm việc trong project |
| [requirements.md](docs/requirements.md) | Phạm vi, yêu cầu, tiêu chí chấp nhận và đối chiếu đề |
| [dataset.md](docs/dataset.md) | Thu thập, chuẩn hóa, chia bộ ảnh, kiểm tra chất lượng |
| [features.md](docs/features.md) | Công thức, cấu hình, số chiều và tính điểm |
| [database.md](docs/database.md) | ERD, từ điển dữ liệu, DDL và truy vấn |
| [architecture.md](docs/architecture.md) | Module, sơ đồ khối, luồng xử lý và quyết định thiết kế |
| [contracts.md](docs/contracts.md) | Kiểu dữ liệu, giao tiếp nội bộ và mã lỗi |
| [implementation-plan.md](docs/implementation-plan.md) | Thứ tự làm, phụ thuộc và điều kiện hoàn thành |
| [testing-evaluation.md](docs/testing-evaluation.md) | Test chức năng và đánh giá truy hồi |
| [report-demo.md](docs/report-demo.md) | Bố cục báo cáo, bằng chứng, kịch bản demo |
| [progress.md](docs/progress.md) | Trạng thái thực tế và điểm bàn giao chat mới |
| [ai-prompts.md](docs/ai-prompts.md) | Prompt chia nhỏ công việc, rà soát và sửa lỗi |

Người mới bắt đầu: requirements → dataset → features → database → architecture → contracts → implementation-plan. AI mỗi lượt: AGENTS → progress → tài liệu liên quan trực tiếp; không cần đọc lại tất cả các file trong mọi lượt.

## 4. Cấu trúc ứng dụng dự kiến

```text
animal-face-cbir/
  README.md
  AGENTS.md
  docs/
  app.py
  src/
    config.py
    preprocessing.py
    feature_extractor.py
    similarity.py
    search_service.py
    ingestion_service.py
    repository.py
    visualization.py
  scripts/
    init_db.py
    import_dataset.py
    extract_features.py
    evaluate.py
  tests/
  migrations/
    001_init.sql
  data/
    original/
    processed/
    queries/
    manifests/
    app.db
  artifacts/
    figures/
    evaluation/
  requirements.txt
  .gitignore
```

Chỉ các file Markdown hiện có trong gói này; những đường dẫn còn lại là thiết kế tương lai. Khi triển khai phải ghi lại phiên bản thư viện thực tế đã kiểm tra. Không tự cho rằng lệnh chạy dự kiến đã chạy thành công.

## 5. Cách bắt đầu

1. Chép các file này vào thư mục gốc project; giữ thư mục docs.
2. Kiểm tra quy định môn học về hệ quản trị CSDL và cách lưu ảnh.
3. Thực hiện T01 rồi T02 trong implementation-plan, với khoảng 30 ảnh thử.
4. Làm được luồng HSV từ ảnh vào đến kết quả trước khi thêm HOG/LBP.
5. Đủ ít nhất 500 ảnh hợp lệ trong gallery trước nghiệm thu cuối.
6. Chạy thực nghiệm; chỉ ghi số liệu thật vào báo cáo.

Lệnh dự kiến sau khi có code:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python scripts/init_db.py
python scripts/import_dataset.py --manifest data/manifests/gallery.csv
python scripts/extract_features.py --bundle baseline-v1
python -m pytest
python -m streamlit run app.py
```

Các tham số dòng lệnh phải được triển khai theo tài liệu hoặc cập nhật tài liệu nếu đã đổi. Chỉ cài dependencies sau khi kích hoạt môi trường ảo theo hệ điều hành đang dùng.

## 6. Hoàn thành toàn project khi nào?

- Gallery có ít nhất 500 ảnh hợp lệ, cùng quy tắc tiền xử lý, đủ ba vector.
- CSDL quản lý metadata, cấu hình, vector và lịch sử truy vấn.
- Truy vấn mới trả về 5 ảnh duy nhất, điểm giảm dần, có điểm thành phần.
- Có minh họa đặc trưng và số liệu thống kê thực tế.
- Có đánh giá trên query tách biệt, cả trường hợp loài chưa xuất hiện.
- Demo chạy lại được từ hướng dẫn cài đặt và bộ dữ liệu bàn giao.
# Xay_dung_CSDL_luu_tru_va_tim_kiem_anh_mat_dong_vat
