# Yêu cầu và phạm vi

## 1. Bài toán

Người dùng có ảnh mặt động vật và muốn tìm những ảnh giống về nội dung thị giác trong bộ ảnh đã lưu. Hệ thống biểu diễn mỗi ảnh bằng đặc trưng số, tính điểm và xếp hạng. Tên file, nhãn loài và mô tả văn bản không được dùng để thay thế phép so sánh nội dung.

Happy path: tải ảnh → xác nhận vùng mặt → chuẩn hóa → trích xuất → đọc gallery hợp lệ → tính điểm → hiển thị top 5 và giải thích điểm.

## 2. Phân biệt yêu cầu đề và lựa chọn triển khai

| Loại | Nội dung |
| --- | --- |
| Đề bắt buộc | Ít nhất 500 ảnh; cùng kích thước; một mặt ở giữa, nhìn thẳng; tỉ lệ tương đối đồng đều |
| Đề bắt buộc | Đặc trưng thể hiện giống/khác, mô tả loại đặc trưng và thống kê |
| Đề bắt buộc | Trích xuất và quản trị đặc trưng trong CSDL |
| Đề bắt buộc | Query mới có thể cùng/khác loài; trả 5 ảnh theo độ tương đồng giảm dần |
| Đề bắt buộc | Sơ đồ khối, chức năng, I/O, quá trình xử lý, kết quả trung gian, đánh giá và demo |
| Đề xuất | RGB 128×128; HSV/HOG/LBP; SQLite; Streamlit; tìm kiếm toàn bộ vector |
| Đề xuất | 500 gallery + 20 validation + 30 test; đây không phải số lượng đề quy định ngoài gallery |

## 3. Phạm vi

Must: quản lý ảnh/loài/nguồn; chuẩn hóa; ba bộ đặc trưng; lưu cấu hình; top 5; thống kê; điểm thành phần; báo cáo đánh giá.

Should: lịch sử truy vấn; nhập lại không tạo bản trùng; loại ảnh khỏi gallery bằng cờ active; xuất kết quả; thử trọng số.

Could: bộ mô tả học sâu để so sánh thêm, vùng chọn mặt tương tác, tìm kiếm gần đúng khi dữ liệu tăng mạnh.

Ngoài phạm vi baseline: xác định đúng cá thể động vật; huấn luyện detector; đăng nhập nhiều người; payment; app điện thoại; realtime camera; yêu cầu luôn trả cùng loài.

## 4. Yêu cầu chức năng

| ID | Yêu cầu | Bằng chứng nghiệm thu |
| --- | --- | --- |
| FR01 | Nhập manifest và ảnh | Metadata xuất hiện trong DB; lỗi từng dòng có lý do |
| FR02 | Chuẩn hóa RGB 128×128 | Kiểm tra kích thước, kênh màu, ảnh xem trước |
| FR03 | Trích xuất/lưu ba vector | Đúng cấu hình, số chiều, hữu hạn, đọc lại khớp |
| FR04 | Tìm top 5 | 5 ID duy nhất, sắp xếp ổn định, không lọc loài |
| FR05 | Minh họa trung gian | Ảnh xử lý, HSV/HOG/LBP, bảng điểm |
| FR06 | Thống kê dữ liệu | Số ảnh hợp lệ, phân bố loài, vector thiếu, thống kê đặc trưng |
| FR07 | Đánh giá | File kết quả từng query, chỉ số tổng hợp, cấu hình thực nghiệm |
| FR08 | Tra cứu lịch sử | Query và kết quả lưu nhất quán trong một giao dịch |

## 5. Acceptance criteria

### AC01 — Bộ dữ liệu
Given gallery chuẩn bị nghiệm thu; When kiểm tra metadata và file; Then có ≥500 ảnh active, quality_status=approved, split=gallery, cùng kích thước và đủ đặc trưng bundle hiện hành. Đánh giá chính diện/tỉ lệ mặt bằng kiểm tra trực quan, không chỉ đếm pixel.

### AC02 — Nhập lại
Given ảnh đã có checksum gốc; When nhập lại cùng file; Then không sinh ảnh trùng và có thông báo skipped. Ảnh gần trùng cần kiểm tra riêng, checksum không phát hiện mọi biến thể.

### AC03 — Tìm kiếm thông thường
Given ≥5 ứng viên đủ đặc trưng; When query hợp lệ được gửi; Then trả 5 ảnh duy nhất, score giảm dần, bằng điểm có thứ tự image_id tăng dần.

### AC04 — Loài chưa có
Given query thuộc loài không nằm trong gallery; When tìm kiếm; Then vẫn so sánh với toàn gallery và trả top 5; không báo lỗi chỉ vì không biết loài.

### AC05 — Dữ liệu sai
Given file hỏng, rỗng hoặc không giải mã được; When tải lên; Then báo INVALID_IMAGE, không ghi query thành công hoặc kết quả giả.

### AC06 — Gallery thiếu
Given <5 ứng viên hợp lệ; When tìm kiếm trong bản demo chuẩn; Then báo INSUFFICIENT_GALLERY và số ứng viên; không nhân bản ảnh để đủ 5.

### AC07 — Cấu hình và vector
Given vector sai config, sai chiều hoặc chứa NaN/Inf; When nạp gallery; Then loại khỏi tập hợp lệ, ghi lý do và không dùng trong phép tính. Nếu thiếu ứng viên, áp dụng AC06.

### AC08 — Tái lập
Given cùng pixel query sau chuẩn hóa, cùng snapshot gallery, cùng cấu hình và trọng số; When chạy lại; Then thứ tự và điểm khớp trong sai số số thực được quy định.

### AC09 — Điểm có thể kiểm chứng
Given bảng điểm ba nhóm; When tính lại weighted sum; Then khớp total_score lưu DB với sai số ≤1e-6. Giao diện chỉ làm tròn khi hiển thị.

## 6. Yêu cầu phi chức năng

- Chạy demo cục bộ không cần gọi API AI trả phí.
- Đo thời gian nạp vector, trích xuất query, xếp hạng và tổng thời gian riêng; chưa ấn định SLA khi chưa đo trên máy thực tế.
- Đường dẫn có thể di chuyển cùng thư mục dữ liệu; không chứa mật khẩu hoặc khóa trong repo.
- Lưu cấu hình để giải thích lại kết quả. Giữ snapshot ảnh/vector được dùng trong bài đánh giá cuối.
- Báo lỗi thân thiện trên UI, lưu chi tiết kỹ thuật trong log.

## 7. Ma trận bám đề

| Mục đề | Tài liệu chính | Sản phẩm thực hiện |
| --- | --- | --- |
| 1 | dataset | Bộ ảnh, manifest, thống kê, mô tả giống/khác |
| 2 | features | Công thức, số chiều, thống kê thực tế |
| 3 | database + contracts | CSDL, chương trình trích xuất, truy vấn quản trị |
| 4 | architecture + features | Pipeline tìm kiếm và top 5 |
| 4a | architecture | Sơ đồ, I/O từng khối |
| 4b | report-demo | Hình và bảng trung gian |
| 4c | testing-evaluation | Kết quả so sánh phương pháp |
| 5 | report-demo | Demo và hướng dẫn chạy |
