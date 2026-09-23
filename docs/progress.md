# Trạng thái hiện tại và bàn giao

## 1. Trạng thái trung thực

**Hiện tại chỉ hoàn thành bộ tài liệu thiết kế. Chưa triển khai ứng dụng hoặc thu thập bộ ảnh.**

| Hạng mục | Trạng thái | Bằng chứng |
| --- | --- | --- |
| Phân tích đề và tiêu chí nghiệm thu | Đã soạn | requirements.md |
| Thiết kế đặc trưng | Đã soạn | features.md |
| Thiết kế CSDL | Đã soạn | database.md |
| Kiến trúc và hợp đồng | Đã soạn | architecture.md, contracts.md |
| Kế hoạch test, báo cáo, prompt | Đã soạn | Các tài liệu tương ứng |
| Kiểm tra cấu trúc gói và DDL minh họa | Chờ kiểm tra khi đóng gói | Không phải test ứng dụng |
| 500 ảnh gallery | Chưa làm | Chưa có manifest/ảnh |
| Code và CSDL ứng dụng | Chưa làm | Chưa có src hoặc app.db |
| Thực nghiệm | Chưa làm | Chưa có metrics |
| Demo | Chưa làm | Chưa có app chạy |

## 2. Các lựa chọn mặc định

Python, SQLite, Streamlit; preprocess-v1 RGB 128×128; HSV 128, HOG 1764, LBP 160; exact scan; weights đều. Chưa có ràng buộc giảng viên về hệ quản trị hoặc ảnh BLOB; cần kiểm tra quy định trước khi chốt T03 nếu có thông tin thêm.

## 3. Nhiệm vụ tiếp theo

T01 — Tạo khung project và môi trường. Sau đó T02 với khoảng 30 ảnh thật. Không bắt đầu bằng tạo đầy đủ giao diện, login hoặc train model.

## 4. Mẫu cập nhật sau mỗi task

```text
Task ID:
Ngày:
Người thực hiện:
Mục tiêu:
File đã đổi:
Quyết định thiết kế mới:
Lệnh đã chạy:
Kết quả thực tế:
Phần chưa kiểm tra:
Lỗi/blocker:
Commit (nếu có):
Task tiếp theo:
File cần đọc ở chat mới:
```

## 5. Nhật ký lỗi

Chưa có lỗi ứng dụng vì chưa triển khai. Khi có lỗi, ghi điều kiện tái hiện, expected/actual, nguyên nhân đã xác nhận, cách sửa và phép kiểm tra lại. Phân biệt giả thuyết với nguyên nhân đã chứng minh.

## 6. Quy tắc hoàn thành

Không đánh dấu task 'done' chỉ vì AI đã sinh code. Dùng 'implemented, unverified' nếu chưa chạy. Mỗi task nghiệm thu phải có bằng chứng tương ứng trong implementation-plan. Không chép số liệu ví dụ thành metric thật.
