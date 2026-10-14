# Hệ CSDL lưu trữ và tìm kiếm ảnh mặt động vật

Bản trên GitHub không bao gồm thư mục `data/`. Để chạy demo với dữ liệu hiện có, cần bổ sung riêng thư mục này, gồm ảnh, manifest, SQLite và calibration tương ứng với profile. Môi trường Python, tệp tạm và trọng số ONNX được bỏ qua theo `.gitignore`.

Cấu hình cải tiến **refined512-v1** giữ ảnh 512×512, ưu tiên vùng trung tâm, HOG hai mức và LBP ba bán kính; GLCM bỏ ASM trùng thông tin. Vẫn sáu nhóm, tổng **11444 chiều**. Thang điểm được hiệu chỉnh từ các cặp gallery, không dùng nhãn loài. Giả định mặt ở giữa ảnh; bản đồ trọng số được hiển thị để kiểm tra. Chi tiết công thức tại [features](docs/features.md); không đồng nhất cải tiến thuật toán với kết luận đã tăng chất lượng thị giác.

Đã nhập và đối soát đủ 600 ảnh/3600 vector, 500 gallery/50 validation/50 test, sai lệch khi tính lại vector bằng 0. Bộ 72 tests và kiểm tra web đạt. Xem [đối chiếu validation](artifacts/evaluation/refined512-v1/comparison_validation.html) hoặc [đối chiếu test](artifacts/evaluation/refined512-v1/comparison_test.html); các cặp ảnh chưa được chấm Visual P@5. Nhật ký và giới hạn ở [progress](docs/progress.md).

Chuẩn bị cấu hình mới nếu chưa có CSDL/calibration:

```powershell
.venv/Scripts/python.exe scripts/prepare_refined_profile.py
```

Lệnh giữ bản sao demo, hiệu chỉnh bằng 500 gallery và nhập dữ liệu theo manifest; chạy lại không ghi đè calibration cũ. Giữ cùng nhau `data/refined512.db` và `data/calibration/refined512-v1/gallery.json`. Bộ expanded bên dưới vẫn có thể chọn để đối chiếu.

Ứng dụng CBIR tính trực tiếp trên ảnh màu **512×512**. Cấu hình đối chiếu **expanded512-v1** có 6 nhóm, tổng **35480 chiều**: HSV 128, HOG 34596, LBP 160, HSV theo vùng 512, Color Moments 36 và GLCM 48. Đã nhập đủ 600 ảnh AFHQ v2/3600 vector: 500 gallery, 50 validation, 50 test. Các cấu hình 3 nhóm cũ được giữ nguyên. Tìm trên toàn bộ gallery hợp lệ, trả 5 ảnh duy nhất; điểm tương đồng không phải xác suất cùng loài.

## Chạy giao diện

Từ thư mục BTL:

```powershell
$env:CBIR_PROFILE='refined512-v1'
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='1'
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Mở http://127.0.0.1:8000. Giữ `.venv`, `animal_face_model/.venv` và Python nền `tmp/uv-python/`. Không cần archive tải nguồn để chạy.

Chọn **6 đặc trưng cải tiến · 512×512** để dùng refined. Chọn **6 đặc trưng · 512×512** để đối chiếu expanded. Điểm số giữa hai cấu hình có thang khác nhau; so sánh ảnh kết quả và đánh giá thị giác. Tạo báo cáo đối chiếu bằng `scripts/compare_visual_profiles.py --split validation`; hướng dẫn chấm tại [testing-evaluation](docs/testing-evaluation.md).

Chọn **6 đặc trưng · 512×512** ở thanh trên. Mục **So sánh nhanh** có từng nhóm, các nhóm bằng nhau và trọng số chọn trên validation (chỉ hiển thị khi kết quả đánh giá còn khớp dữ liệu/config). Có sáu thanh trọng số, bảng điểm/đóng góp, biểu đồ vector mới và **Xuất kết quả JSON**. Bộ trọng số khởi đầu dùng cả sáu nhóm, không được mô tả là đã tối ưu. Công thức tại [features](docs/features.md); kết quả và giới hạn tại [testing-evaluation](docs/testing-evaluation.md).

Dashboard đếm ứng viên có ảnh và vector hợp lệ; liệt kê image_id/đường dẫn/lý do khi loại. Thời gian phản hồi tách riêng truy hồi, tách nền và tạo preview; tổng phía máy chủ chưa bao gồm mạng/render trình duyệt.

Frontend có nền cực quang/hạt chuyển động, vòng HSV/HOG/LBP, chuyển trang, thẻ ảnh nghiêng theo chuột, hiệu ứng quét và biểu đồ động. Nút **Animation** ở thanh trên bật/tắt chuyển động và nhớ lựa chọn; trên điện thoại là biểu tượng tia sáng. Giao diện tự tắt chuyển động khi thiết bị bật giảm chuyển động, và tạm dừng hiệu ứng khi tab bị ẩn.

Font giao diện dùng Be Vietnam Pro; điểm số/ID/mã cấu hình dùng Fira Code. Font lưu trong `frontend/static/fonts/`, dùng được khi offline; nguồn và giấy phép tại [fonts/README](frontend/static/fonts/README.md).

## Tách nền và lưu đặc trưng trong hệ thống

1. Vào **Xử lý ảnh**. Chọn toàn bộ ảnh hoặc chạy thử 5 ảnh.
2. Nhấn **1. Tách nền** để chạy model ONNX đã có; mask RGBA 512×512 được lưu riêng dưới `data/background_removed/all-images/`.
3. Nhấn **2. Trích xuất & lưu CSDL** sau khi tách nền hoặc chỉnh mask bằng tay. Hệ thống ghép trắng, tính đặc trưng 512 và tự nhập SQLite. Nút **Chạy cả hai bước** thực hiện liên tiếp bước 2 và 3.
4. Xem cặp ảnh gốc/mask và duyệt ảnh đạt yêu cầu. Mask mới nhập có trạng thái pending; chỉ gallery approved tham gia truy hồi.
5. Chọn **Ảnh tách nền · 512×512** ở thanh trên để tìm trong CSDL tách nền. Query thường được tự tách nền; PNG alpha hợp lệ được dùng trực tiếp.

Model và trọng số giữ nguyên. Chạy lại tái sử dụng mask đã kiểm tra và bỏ qua checksum đã nhập. Nếu chỉnh mask, giữ nguyên RGB/kích thước và thay alpha trong file mask; lần nhập sau tạo phiên bản mới, giữ ảnh/vector cũ cho lịch sử. Xem [hướng dẫn tách nền](docs/background-import.md).

Hiện đã chạy thật 5 mask, nhập 15 vector; kiểm tra ngày 13/10/2026 có **2 gallery approved/active và 3 rejected/inactive**. **Chưa chạy model toàn bộ 600 ảnh**, nên profile tách nền hiện chưa đủ top-5 hoặc 500 gallery để nghiệm thu. Native512 và expanded512 có đủ 500 gallery. Không tự duyệt lại mask đã bị loại.

## Dữ liệu cần giữ

| Đường dẫn | Vai trò |
| --- | --- |
| `data/original/` | 600 ảnh nguồn RGB 512×512 giữ nguyên byte; native512 dùng trực tiếp để tính, không nhân đôi thành bản 128 |
| `data/native512.db` | 600 ảnh / 1800 vector của native512-v1 |
| `data/expanded512.db` | 600 ảnh / 3600 vector của expanded512-v1; dùng chung ảnh nguồn, CSDL/config riêng |
| `data/background_removed/all-images/` | Mask RGBA để xem/chỉnh bằng tay |
| `data/background_removed/versions/` | Snapshot mask bất biến đã dùng tính vector; giữ để đọc lịch sử |
| `data/processed/background512-white-v1/` | RGB nền trắng 512×512 của mask đã nhập |
| `data/background512_white.db` | Metadata và vector của background512-white-v1 |
| `data/background_removed/queries/`, `data/queries/` | Mask/query xử lý được tham chiếu hoặc tái sử dụng |
| `data/manifests/`, `data/review/`, `data/statistics/` | Nguồn, quyết định duyệt, kiểm tra và thống kê thật |
| `data/processing_jobs/` | Trạng thái, tiến độ và log tác vụ |
| `data/backups/before-native512-20261010.zip` và JSON | Bản khôi phục 600 ảnh/CSDL 128 trước chuyển sang 512 |
| `data/backups/before-expanded512-20261013/` | Bản sao hai SQLite cũ trước migration mở rộng |

Giữ code `backend/`, `frontend/`, `animal_face_model/`, `migrations/`, `scripts/`, `tests/`, `docs/`. Baseline 128 không bị đổi công thức; để dùng lại cần khôi phục dữ liệu cũ từ ZIP vào vị trí riêng. Không so sánh vector giữa các profile. Nguồn từng ảnh: [CSV nguồn](data/manifests/frontal512_sources.csv); phân bố/duyệt: [dataset](docs/dataset.md); giấy phép: [sources](docs/sources.md).

## Chạy bằng lệnh

```powershell
# Chạy hai bước cho cả manifest 600 ảnh; cần thời gian xử lý CPU
.venv\Scripts\python.exe scripts\process_dataset.py pipeline
# Hoặc riêng từng bước
.venv\Scripts\python.exe scripts\process_dataset.py remove_background
.venv\Scripts\python.exe scripts\process_dataset.py extract_features
# Thử 5 ảnh
.venv\Scripts\python.exe scripts\process_dataset.py pipeline --limit 5
```

## Kiểm tra

Nhập và đánh giá cấu hình mở rộng:

```powershell
.venv\Scripts\python.exe scripts/import_dataset.py --profile expanded512-v1
.venv\Scripts\python.exe scripts/evaluate.py --profile expanded512-v1 --split validation
.venv\Scripts\python.exe scripts/evaluate.py --profile expanded512-v1 --split test
# Dùng CBIR_PROFILE đang chọn; xuất min/max/mean/std và thống kê vector
.venv\Scripts\python.exe scripts/export_statistics.py
```

CSV/JSON đánh giá nằm trong `data/evaluation/expanded512-v1/`; thống kê ở `data/statistics/expanded512-v1/`. Pool CSV để chấm thị giác chưa được điền thay người đánh giá; cách chấm và tính Visual P@5 ở testing-evaluation.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
.venv\Scripts\python.exe scripts\verify_web_runtime.py
.venv\Scripts\python.exe scripts\verify_frontal_dataset.py --profile expanded512-v1
```

Web test dùng bản sao SQLite theo CBIR_PROFILE. Dataset test đối chiếu toàn bộ nguồn/pixel/metadata và tính lại vector. Kết quả thật và phần chưa kiểm tra: [progress](docs/progress.md). Đã chạy đánh giá theo nhãn cho cấu hình mở rộng trên 50 validation + 50 test; chưa có Visual P@5. Số liệu 128 cũ không áp dụng cho cấu hình mới.

## Dọn dữ liệu dư

Runtime 128, nguồn tải chưa dùng và bản sao dư đã chuyển ra `../BTL_luu_tru_20261010/`; ảnh gốc hiện hành, model và bản khôi phục được giữ. Nhật ký chuyển runtime: [native512-cleanup](docs/native512-cleanup-20261010.json). Lần dọn bổ sung chuyển 43 file cache/build/log cũ và thư mục rỗng ra `../BTL_luu_tru_20261010/obsolete-after-project-cleanup/`; [nhật ký và kiểm tra](docs/project-cleanup-20261010.json).

Kiểm duyệt tự động đã chặn lệnh xóa hàng loạt (`blocked by policy`), nên **chưa xóa vĩnh viễn, chưa giải phóng dung lượng ổ đĩa**. Người dùng có thể xem phạm vi và xóa thủ công:

```powershell
.\scripts\cleanup_obsolete_data.ps1
.\scripts\cleanup_obsolete_data.ps1 -Purge
```

Script kiểm tra checksum 600 ảnh hiện hành, bản ZIP phục hồi và năm thư mục dư cố định (gồm các file dư đã chuyển ở lượt dọn bổ sung) trước khi xóa.
