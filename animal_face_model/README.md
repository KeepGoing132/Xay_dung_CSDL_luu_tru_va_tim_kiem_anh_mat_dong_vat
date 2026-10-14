# Tách nền ảnh động vật

Model `birefnet-general-lite.onnx` và môi trường `.venv` đã được đưa về thư mục này. Dùng CPU với rembg 2.0.67 và ONNX Runtime 1.31.0. Đây là model pretrained, không có bước training trong project.

## Chạy một ảnh

Từ thư mục gốc BTL:

```powershell
$env:PYTHONUTF8='1'
animal_face_model\.venv\Scripts\python.exe animal_face_model\remove_background.py --input data\original\gallery\cat\pixabay_cat_003019.png --output data\background_removed\one-image
```

## Chạy cả thư mục

```powershell
animal_face_model\.venv\Scripts\python.exe animal_face_model\remove_background.py --input data\original --output data\background_removed\all-images --manifest data\manifests\frontal512_manifest.csv --resume
```

Script duyệt ảnh trong thư mục con, giữ cấu trúc thư mục và thêm `.png` vào tên gốc để tránh trùng tên giữa JPG/PNG. Dùng `--limit 5` để chạy thử, `--threads 4` để giới hạn số luồng CPU. Kết quả giữ kích thước sau EXIF và pixel RGB gốc; chỉ bổ sung alpha để tạo nền trong suốt. Không resize xuống 128×128 hoặc chuyển sang ảnh xám.

Mỗi lần chạy tạo báo cáo JSON có đường dẫn nguồn/đầu ra tương đối, checksum, kích thước, khoảng alpha và lỗi cụ thể. Không có `--resume`, file đã tồn tại khiến lệnh dừng trước xử lý. Với `--resume`, chỉ tái sử dụng mask đã kiểm tra kích thước, RGB khớp nguồn và alpha hợp lệ; file không hợp lệ báo lỗi để sửa. `--manifest` giới hạn đúng các nguồn trong manifest. `--progress-file` ghi sự kiện JSONL để web đọc tiến độ. Có ảnh lỗi thì exit code 1, ảnh thành công vẫn được ghi nhận. Cần xem lại mask vì model có thể bỏ sót lông, tai hoặc vùng mặt.

Đã tích hợp vào mục **Xử lý ảnh** trên web: tách nền, trích xuất/lưu SQLite hoặc chạy cả hai bước. Profile hiện dùng `background512-white-v1`; [hướng dẫn](../docs/background-import.md). CLI điều phối: `.venv\Scripts\python.exe scripts\process_dataset.py pipeline`. Đã chạy thật 5 ảnh và nhập 15 vector; chưa tách/nhập toàn bộ 600 ảnh. Gallery/query phải cùng pipeline, không dùng vector native/baseline để so với query đã tách nền. Model/trọng số giữ nguyên.

## Khôi phục môi trường

```powershell
powershell -ExecutionPolicy Bypass -File animal_face_model\setup.ps1
```

Cần `uv` và model ONNX cục bộ. Môi trường hiện có vẫn dùng Python nền trong `tmp/uv-python/`; giữ thư mục đó. Thư viện tách nền được cài riêng, không cần thêm vào môi trường chạy web.

## Model và nguồn

Model có 224.005.088 byte. Script kiểm tra SHA-256 trước khi khởi tạo phiên chạy; thiếu/sai model thì dừng. Chỉ dùng model cục bộ đã xác minh.

- SHA-256: `5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333`.
- MD5: `4fab47adc4ff364be1713e97b7e66334`.
- [BiRefNet chính thức](https://github.com/ZhengPeng7/BiRefNet).
- [Định nghĩa model trong rembg 2.0.67](https://github.com/danielgatis/rembg/blob/v2.0.67/rembg/sessions/birefnet_general_lite.py).
