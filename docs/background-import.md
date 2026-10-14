# Tách nền → trích xuất → lưu SQLite

Luồng đang dùng `background512-white-v1`: model giữ nguyên kích thước/RGB và thêm alpha; ảnh tách nền được ghép trắng, crop theo manifest, giữ RGB 512×512 rồi tính đặc trưng. Thuật toán/số chiều nằm trong [features](features.md), hợp đồng API trong [contracts](contracts.md).

## Trên giao diện

Mở http://127.0.0.1:8000 rồi vào **Xử lý ảnh**. Có ba nút: **1. Tách nền**, **2. Trích xuất & lưu CSDL**, **Chạy cả hai bước**. Chọn toàn bộ 600 ảnh hoặc thử 5 ảnh. Tiến độ/log/lỗi được giữ khi refresh; chỉ một tác vụ dataset chạy cùng lúc. Nút dừng giữ ảnh/vector đã lưu thành công để chạy lại.

Bước 1 gọi `animal_face_model/remove_background.py` trong môi trường model riêng, không huấn luyện lại và không thay trọng số. Bước 2 tự tạo manifest ảnh tách nền, lưu PNG xử lý, metadata và ba vector vào SQLite. Chạy bước 1 riêng chưa ghi vector vào DB.

Sau nhập, xem cặp gốc/mask trên trang, chọn ảnh rồi duyệt hoặc loại. Chỉ gallery active/approved có đủ đặc trưng tham gia truy hồi. Ảnh mới mặc định pending vì nguồn đã duyệt không có nghĩa mask chắc chắn tốt. Có bộ lọc ảnh đã tách nền và phân trang để duyệt.

Chọn **Ảnh tách nền · 512×512** ở thanh trên để dùng CSDL này. Query thường được tự crop/chuẩn hóa 512, chạy model rồi đi cùng pipeline nền trắng; PNG có alpha hợp lệ bỏ qua model. Tìm kiếm vẫn so sánh toàn bộ gallery hợp lệ, không lọc theo loài.

## File đầu vào và đầu ra

- Nguồn: `data/original/`, manifest `data/manifests/frontal512_manifest.csv`.
- Mask có thể chỉnh: `data/background_removed/all-images/{split}/{nhóm}/{tên-gốc}.png`. Tên gốc giữ đuôi file nên một PNG nguồn sẽ có tên mask `.png.png`.
- Snapshot mask đã tính đặc trưng: `data/background_removed/versions/{split}/{nhóm}/{tên-mask}.{sha16}.png`.
- RGB nền trắng 512: `data/processed/background512-white-v1/`.
- SQLite: `data/background512_white.db`.
- Manifest: `data/manifests/background512_white_manifest.csv`; báo cáo `.import.json` cùng vị trí.
- Job/log/tiến độ: `data/processing_jobs/`.

Sau khi sửa bằng tay, giữ đúng kích thước và RGB nguồn, chỉ sửa alpha trong file mask. Chạy **Trích xuất & lưu CSDL**: checksum mới tạo ảnh/vector mới ở trạng thái pending; bản cũ cùng group_id chuyển inactive/rejected nhưng vẫn giữ để lịch sử hoạt động. Duyệt lại mask mới. Không xóa `versions/` hoặc ảnh processed đang được DB tham chiếu.

## Chạy bằng CLI

Từ gốc project, môi trường web điều phối model riêng:

```powershell
.venv\Scripts\python.exe scripts\process_dataset.py pipeline
.venv\Scripts\python.exe scripts\process_dataset.py remove_background
.venv\Scripts\python.exe scripts\process_dataset.py extract_features
# Thử 5 ảnh, cho phép bộ mask chưa đầy đủ
.venv\Scripts\python.exe scripts\process_dataset.py pipeline --limit 5
```

Hoặc gọi trực tiếp công cụ model rồi nhập:

```powershell
animal_face_model\.venv\Scripts\python.exe animal_face_model\remove_background.py --input data\original --output data\background_removed\all-images --manifest data\manifests\frontal512_manifest.csv --resume
.venv\Scripts\python.exe scripts\import_background_dataset.py
```

`--resume` chỉ tái sử dụng cutout khi kích thước, RGB và alpha hợp lệ. Không ghi đè ngầm file không hợp lệ. Mỗi ảnh lỗi có đường dẫn/lý do; exit code khác 0 khi lỗi. Trực tiếp nhập bằng `--allow-partial` chỉ dành cho thử nghiệm; nhập đầy đủ phải có đủ mask theo manifest. `--reviewed` chỉ dùng sau khi thực sự xem mask: kế thừa trạng thái nguồn, không tự duyệt nguồn pending/rejected.

Mỗi lần nhập lại sao lưu SQLite đích thành `.before-import-<thời điểm>.db`. Checksum đã nhập được skipped, quyết định duyệt hiện có được giữ. Không ghi đè `native512.db`, `app.db` hoặc manifest nguồn. Thông tin nguồn/giấy phép được kế thừa và bổ sung ghi chú mask/ghép trắng; ảnh gốc không đổi.

## Trạng thái đã kiểm tra

Đã chạy thật model 5 ảnh, có 5 mask RGBA 512 và 15 vector trong SQLite; cả 5 được xem/duyệt để thử. Chạy lại pipeline từ web không sinh bản trùng. Đã thử query thường ngoài gallery: tự tách nền, lưu query và trả đúng 5 kết quả duy nhất. **Chưa chạy toàn bộ 600 mask**, nên profile này chưa đủ 500 gallery nghiệm thu. Chưa đánh giá đầy đủ chất lượng truy hồi sau tách nền.

Các profile `baseline-v1` và `background-white-v1` 128 vẫn giữ tương thích code. Dữ liệu 128 cũ đã lưu ngoài runtime/bản ZIP phục hồi; không trộn vector với các profile 512.
