# Kế hoạch triển khai theo nhiệm vụ

## 1. Cách dùng

Thực hiện theo phụ thuộc; không giao một prompt 'làm hết project'. Mỗi nhiệm vụ phải có đầu vào, sản phẩm và bằng chứng kiểm tra. Trạng thái thật lưu ở progress.md. Bảng dưới chưa cam kết thời gian hoặc người làm; owner điền khi phân công.

## 2. Danh sách công việc

| ID | Nhiệm vụ | Phụ thuộc | Owner | Sản phẩm |
| --- | --- | --- | --- | --- |
| T01 | Khởi tạo môi trường, cấu trúc, config | Không | Chưa gán | Khung ứng dụng và dependencies khóa phiên bản |
| T02 | 30 ảnh thử, manifest và preprocessing | T01 | Chưa gán | Ảnh chuẩn hóa, test ảnh lỗi/crop |
| T03 | Schema và repository nền | T01 | Chưa gán | DB tạo được, CRUD cần thiết, test ràng buộc |
| T04 | HSV và lưu vector | T02,T03 | Chưa gán | Extractor màu, round-trip DB |
| T05 | Luồng tìm kiếm HSV bằng script | T04 | Chưa gán | Top 5 từ input ảnh đến DB |
| T06 | HOG, LBP, bundle và ranking kết hợp | T05 | Chưa gán | Ba vector, điểm thành phần |
| T07 | Hoàn thiện ≥500 gallery và query split | T02,T06 | Chưa gán | Manifest sạch và vector đủ |
| T08 | UI và minh họa trung gian | T06 | Chưa gán | Upload, top 5, bảng điểm, figures |
| T09 | Lịch sử, giao dịch, xử lý lỗi tích hợp | T03,T08 | Chưa gán | Luồng hoàn chỉnh bền vững |
| T10 | Validation, chốt cấu hình, test cuối | T07,T09 | Chưa gán | Kết quả thực nghiệm và phân tích |
| T11 | Báo cáo, demo, đóng gói | T10 | Chưa gán | Tài liệu, code, DB, ảnh, hướng dẫn |

T05 là bản tạm chỉ HSV, chưa đáp ứng đủ hợp đồng bundle baseline-v1. Dùng bundle thử nghiệm riêng hoặc script standalone; không đánh dấu chức năng baseline hoàn thành ở bước này. T06 thay bằng contract chuẩn ba nhóm.

## 3. Nghiệm thu từng nhiệm vụ

### T01 — Khởi tạo
- Tạo thư mục theo README; giữ tài liệu tại root/docs.
- Tạo môi trường ảo, chọn versions thực tế cài được và ghi requirements.
- Tạo config tập trung: data root, DB path, preprocess version và bundle.
- Thêm ignore cho môi trường ảo, cache, dữ liệu tải lớn và DB runtime nếu không định version chúng bằng Git.
- Nghiệm thu: import dependencies thành công, chạy một test smoke có ý nghĩa; README có lệnh đúng môi trường.

### T02 — Dữ liệu thử
- Thu thập ảnh thật, ghi nguồn; chưa cần đủ 500.
- Cài pipeline EXIF → RGB → crop vuông → resize → checksum.
- Xem contact sheet; sửa crop nếu mặt quá nhỏ/lệch.
- Nghiệm thu: ảnh chuẩn hóa đúng shape/type; invalid crop không bị sửa âm thầm; ảnh lỗi có thông báo.

### T03 — Repository
- Chép DDL từ database.md thành migration ban đầu.
- Bật khóa ngoại trên từng connection, dùng SQL tham số hóa.
- Viết lưu/đọc metadata, config, vector và thống kê.
- Nghiệm thu: unique checksum, FK, dimension validation, skip khi nhập lại.

### T04 — HSV
- Hiện thực đúng 128 bin chung, cùng miền màu.
- Lưu vector và đọc lại; kiểm tra sum=1, finite.
- Nghiệm thu: ảnh màu đơn tạo histogram tập trung; thay tên file không đổi vector.

### T05 — Tìm màu xuyên suốt
- Nhập ảnh thử, trích HSV trước.
- Query mới dùng cùng pipeline; intersection; top 5.
- Nghiệm thu: chạy từ file query thật đến 5 file kết quả; không dùng label để chọn ứng viên.

### T06 — Bộ đặc trưng đủ
- Thêm HOG 1764 và LBP 160 theo cấu hình, không lấy default khác.
- Viết compare/rank và kiểm tra tie-break, zero HOG, weights.
- Đăng ký ba config; service dùng exact IDs.
- Nghiệm thu: các test vector và toy ranking trong testing-evaluation đạt.

### T07 — Dữ liệu đầy đủ
- Mở rộng nguồn, rà soát ảnh trùng và chất lượng.
- Hoàn thành gallery ≥500; tách validation/test theo group.
- Chạy batch extraction có resume theo cặp image_id/config_id; xuất failed list.
- Nghiệm thu: SQL và kiểm tra vector xác nhận ≥500 ứng viên thực sự dùng được.

### T08 — Giao diện
- Tab dataset: số lượng, trạng thái, gallery.
- Tab search: ảnh upload, crop, weights, top 5.
- Tab analysis: histogram/HOG/LBP, điểm, thời gian.
- Nghiệm thu: hiển thị đúng ID và score do service trả, không tính lại riêng trong UI.

### T09 — Độ tin cậy
- Lưu query và results một giao dịch; lịch sử mở lại được.
- Mất file, thiếu vector, cấu hình sai, DB lỗi được báo đúng.
- Nghiệm thu: rollback không để query nửa chừng, không trả ảnh trùng để đủ 5.

### T10 — Thực nghiệm
- Tạo judgments theo tiêu chí đã chốt.
- So sánh từng đặc trưng và kết hợp trên cùng query/candidate set.
- Chọn trọng số bằng validation, đóng băng rồi chạy test.
- Xuất per-query metrics, thời gian, failures và environment.
- Nghiệm thu: có số liệu thật, không dùng query test để chọn cấu hình cuối.

### T11 — Bàn giao
- Dựng báo cáo theo report-demo; chụp bằng chứng từ lần chạy thật.
- Kiểm tra lại từ môi trường mới hoặc thư mục bản sao theo README.
- Chuẩn bị backup DB+ảnh, video dự phòng nếu môn học cần.
- Nghiệm thu: người khác làm theo hướng dẫn có thể tìm ảnh và xem CSDL.

## 4. Estimate và capacity

Ước tính bằng giờ công cho từng T sau khi biết số người và kinh nghiệm. Bao gồm tìm ảnh, duyệt/crop, code, ghép module, test và viết báo cáo. Tổng giờ công không bằng số ngày lịch nếu có phụ thuộc hoặc mọi việc dồn vào một người.

Mẫu theo dõi: ID | owner | estimate giờ | thực tế giờ | blocker | ngày dự kiến. Không điền con số cam kết khi chưa biết deadline. Sau T02 và T05, dùng thời gian thật để cập nhật estimate cho phần còn lại.

## 5. Git và chat

Mỗi nhiệm vụ chạy đúng tạo một mốc commit theo yêu cầu người quản lý project. Xem git status/diff trước commit. Không add toàn bộ dữ liệu lớn hoặc bí mật. Git lưu code/tài liệu; backup ảnh và DB bằng cơ chế riêng có kiểm tra phục hồi.

Mở chat mới khi chuyển nhiệm vụ độc lập. Trước đó cập nhật progress: commit gần nhất, files liên quan, lệnh đã chạy, lỗi còn lại, next task. Không cần xóa chat cũ và không cần đổi chat giữa các lần sửa cùng một lỗi.
