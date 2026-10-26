# FaunaFind — truy hồi ảnh mặt động vật

Ứng dụng dùng **bốn nhóm đặc trưng truyền thống**, profile mặc định
`foreground4-hogpca512-v1`, tổng **5.216 chiều**:

| Nhóm | Số chiều | Thông tin chính | Trọng số mặc định |
|---|---:|---|---:|
| HOG-PCA | 512 | Bố cục hướng cạnh theo không gian | 8/17 ≈ 47,06% |
| HSV theo vùng | 512 | Phân bố màu trong các vùng ảnh | 3/17 ≈ 17,65% |
| Dense RootSIFT + VLAD | 4.096 | Mẫu gradient cục bộ, gộp theo cụm | 4/17 ≈ 23,53% |
| Gabor | 96 | Kết cấu theo hướng và tần số | 2/17 ≈ 11,76% |

Gallery và query cùng qua EXIF → crop vuông → RGB512 → BiRefNet-general-lite/DirectML
→ ghép trắng → bốn vector → điểm tương đồng từng nhóm → tổng có trọng số → top 5 ảnh.
Không lọc nhãn loài trước khi xếp hạng. Điểm tương đồng không phải xác suất cùng loài.
HOG-PCA, codebook VLAD và thang điểm chỉ được học từ gallery.

## Chạy ứng dụng

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_app.ps1
```

Mở `http://127.0.0.1:8000`. Dùng `-Port 8765` để đổi cổng. Chạy trực tiếp cũng dùng
cùng profile mặc định:

```powershell
.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

`CBIR_PROFILE` cho phép chọn profile khác đã chuẩn bị; `-Baseline` chọn
`foreground4-v1` với HOG gốc 9.864 chiều, tổng 14.568 chiều. CSDL mặc định là
`data/foreground4_hogpca512.db`; baseline dùng `data/foreground4.db`.

## Dữ liệu và nguồn ảnh

- `data/dataset512-left/images512`: 831 ảnh RGB 512×512 của 10 loài.
- 781 ảnh gallery; 50 query đã dùng để chọn cấu hình được coi là **validation**.
- `data/dataset512-test/manifest-test.csv`: hồ sơ nguồn của tập 50 ảnh tách riêng.
  Không được coi đây là một test độc lập mới nếu ảnh trùng các query validation.
- `data/dataset512-left/manifest.csv`, `orientation-log.csv`, `quality-review.csv`,
  `inventory.csv`, `ATTRIBUTION.html`, `AFHQ-NOTICE.txt`: giữ nguồn, giấy phép, checksum
  và lịch sử chọn ảnh. Các hồ sơ cũ được giữ tại `data/provenance/previous-manifests`.
- Mask gallery: `data/background_removed/foreground4-v1`; mask của 50 query cũ:
  `data/background_removed-test/foreground4-v1`.
- Manifest runtime: `data/manifests/foreground4_hogpca512_sources.csv` và
  `foreground4_hogpca512_manifest.csv`. Chỉ gallery approved + active được truy hồi.

## Chuẩn bị dữ liệu

Giữ `.venv`, `animal_face_model/.venv`, `animal_face_model/runtime-directml`, trọng số
ONNX và `tmp/uv-python`: đây là các thành phần runtime. Cài bằng
`scripts/bootstrap.ps1` và `animal_face_model/setup.ps1`. Model không tự chuyển sang CPU
khi GPU DirectML lỗi.

Nếu đã có model PCA/calibration đóng băng:

```powershell
.venv/Scripts/python.exe scripts/prepare_dataset.py --action sources
.venv/Scripts/python.exe scripts/prepare_dataset.py
```

Khi dựng lại từ đầu, chuẩn bị baseline trước, sau đó học PCA từ gallery:

```powershell
$env:CBIR_PROFILE = 'foreground4-v1'
.venv/Scripts/python.exe scripts/prepare_dataset.py
Remove-Item Env:CBIR_PROFILE
.venv/Scripts/python.exe scripts/prepare_hog_pca.py
```

Script PCA khảo sát 128/256/512 chiều trên validation và ghi lựa chọn ra báo cáo;
không tự đổi profile mặc định khi khởi động. Không ghi đè model/calibration đã đóng băng
khi dữ liệu gallery thay đổi; cần tạo phiên bản mới.

## Đánh giá và kiểm tra

```powershell
.venv/Scripts/python.exe scripts/evaluate.py --split validation --leave-one-out
.venv/Scripts/python.exe scripts/verify_project.py --require-ready
.venv/Scripts/python.exe scripts/check_dataset_logs.py
.venv/Scripts/python.exe -m pytest
node --test tests/frontend_input.test.cjs tests/frontend_render.test.cjs
```

P@5 cùng loài trên 50 validation của cấu hình bốn bộ là **82%**, Top-1 **96%** trong
đối chứng đã có. Đây là kết quả validation; không phải cam kết chất lượng trên ảnh mới
hoặc đánh giá tương đồng thị giác do con người chấm.

Kết quả mới và kiểm tra đồng bộ được ghi tại
`data/evaluation/foreground4-hogpca512-v1/`. Các tên run dùng tiền tố `ALL4_`.

Các báo cáo, CSDL và thí nghiệm đã nghỉ dùng được gom vào
`data/provenance/retired-artifacts-20261021.zip`; tệp làm việc cũ ở
`retired-workfiles-20261021.zip`. Hai gói đã được kiểm tra checksum trước khi dọn bản rời.
Đây là dữ liệu khôi phục lịch sử, không phải cấu hình đang chạy.
