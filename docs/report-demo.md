# Báo cáo và demo

## 1. Bố cục báo cáo

### Chương 1 — Bài toán
Giới thiệu tìm kiếm ảnh theo nội dung, đầu vào/đầu ra và phạm vi. Nhắc rõ ảnh query có thể khác loài. Dẫn lại các yêu cầu đề, phân biệt phương án nhóm lựa chọn với điều kiện bắt buộc.

### Chương 2 — Bộ dữ liệu
Nguồn thật, số ảnh trước/sau lọc, phân bố loài, tiêu chí mặt chính diện, chuẩn hóa. Chèn contact sheet và ảnh trước/sau crop. Mô tả điểm giống/khác giữa mặt động vật. Giải thích chia gallery/validation/test và cách chống trùng.

### Chương 3 — Đặc trưng
HSV/HOG/LBP: ý nghĩa, công thức, tham số, số chiều, chuẩn hóa. Chèn giá trị thống kê tính từ bộ ảnh thật. Có ví dụ vector/ảnh trực quan. Không sao chép toàn bộ hàng nghìn số vào phần chính.

### Chương 4 — CSDL
ERD, từ điển dữ liệu, PK/FK/UNIQUE/CHECK, chuẩn hóa các bảng, lưu ảnh/vector, SQL quản trị, transaction và backup. Giải thích vì sao tính similarity ở ứng dụng nhưng vector vẫn được quản trị trong DB.

### Chương 5 — Hệ thống và truy vấn
Sơ đồ khối có nhãn dữ liệu, chức năng/I/O từng module. Hai pipeline nhập và tìm. Công thức similarity, trọng số, tie-break và các lỗi đầu vào. UI và lịch sử.

### Chương 6 — Kết quả thực nghiệm
Cấu hình máy/phần mềm, gallery và query, rubric relevance, các phương pháp so sánh. Bảng số liệu thật, điểm từng query, P@5, thời gian, unknown-species, case thất bại. Nêu hạn chế cách gán nhãn và kích thước tập test.

### Chương 7 — Kết luận
Những yêu cầu đã hoàn thành và bằng chứng. Phần chưa làm/giới hạn. Hướng phát triển chỉ ghi đề xuất, không mô tả như đã triển khai.

Phụ lục: hướng dẫn cài đặt, schema, manifest, tham số chạy, bảng kết quả chi tiết, phân công thực tế, tài liệu tham khảo.

## 2. Danh sách hình/bảng cần chuẩn bị

| Mã | Bằng chứng | Nguồn tạo |
| --- | --- | --- |
| F01 | Contact sheet ảnh chuẩn hóa | Bộ ảnh gallery |
| F02 | Trước/sau crop và resize | Preprocessing thật |
| F03 | Histogram HSV, HOG, LBP | Extractor thật |
| F04 | ERD | Schema cuối |
| F05 | Sơ đồ khối | Kiến trúc cuối |
| F06 | Query và top 5 | Ứng dụng chạy thật |
| F07 | Trường hợp tìm sai | Tập test |
| T01 | Số lượng ảnh và trạng thái | SQL/manifest |
| T02 | Thống kê đặc trưng | Script statistics |
| T03 | Điểm thành phần ứng viên | SearchResults |
| T04 | So sánh phương pháp | Evaluation CSV |

## 3. Một ví dụ truy vấn phải trình bày

1. Ảnh đầu vào và nguồn query.
2. Vùng mặt được chọn, ảnh RGB 128×128.
3. Bundle/config ID và vector lengths.
4. Histogram màu, HOG visualization, LBP image/histogram.
5. Một bảng điểm thành phần của các ứng viên, không chỉ top 1.
6. Công thức tính tổng được thay số thật cho một ảnh.
7. Top 5 theo điểm giảm dần.
8. Nhận xét: ảnh nào giống ở đâu, ảnh nào sai và vì sao.

## 4. Kịch bản demo đề xuất 8–10 phút

| Thời lượng | Hoạt động | Điểm cần chứng minh |
| --- | --- | --- |
| 1 phút | Giới thiệu bài toán và phạm vi | CBIR, top 5, ≥500 ảnh |
| 1 phút | Xem DB, số lượng và vector | Có hệ CSDL thực sự |
| 2 phút | Query quen thuộc | Pipeline đầy đủ và kết quả |
| 2 phút | Mở phân tích điểm | Có minh họa trung gian |
| 1 phút | Query loài chưa có | Không phụ thuộc nhãn |
| 1 phút | Lỗi đầu vào hoặc thiếu dữ liệu | Xử lý lỗi có kiểm soát |
| 1–2 phút | Bảng đánh giá và hạn chế | Có đo chất lượng thật |

Thời lượng là gợi ý; điều chỉnh theo yêu cầu lớp. Chuẩn bị ảnh query sẵn nhưng cũng cho phép thử ảnh mới đạt chuẩn. Không dùng ảnh trong gallery để trình diễn rồi gọi đó là đánh giá độc lập.

## 5. Câu hỏi thường gặp khi bảo vệ

- Vì sao không chỉ phân loại loài? Vì đề yêu cầu trả ảnh tương đồng; ảnh khác loài vẫn có thể giống về đặc trưng.
- Vì sao phải chuẩn hóa mặt? Vì vị trí, tỉ lệ, nền và góc nhìn ảnh hưởng các đặc trưng.
- Vì sao ba đặc trưng? Màu, cạnh/hình dạng và kết cấu bổ sung nhau; hiệu quả phải kiểm tra thực nghiệm.
- Vì sao SQL không trực tiếp tính cosine? Baseline quản trị vector trong DB và tính toán bằng ứng dụng; vẫn có schema, transaction và truy vấn quản trị. Nếu đề yêu cầu phép tính trong DB thì cần thay thiết kế.
- Điểm 0.9 có nghĩa 90% đúng không? Không; đó là điểm theo công thức, không phải xác suất.
- Khi thêm ảnh thì làm gì? Chuẩn hóa và trích vector cùng config, lưu DB, cập nhật gallery/cache.
- Khi đổi cell HOG thì sao? Config mới, dimension có thể đổi; tính lại vector, không trộn với config cũ.

## 6. Gói bàn giao

- Code nguồn, requirements khóa phiên bản, migrations và tests.
- README có lệnh thực tế và đường dẫn tương đối.
- DB cùng ảnh được phép bàn giao; nếu không thể kèm ảnh, có hướng dẫn nguồn và tái dựng rõ ràng.
- Manifest split/crop/source, cấu hình feature, báo cáo đánh giá.
- Báo cáo, hình minh họa và video nếu lớp yêu cầu.
- Backup và hướng dẫn phục hồi; thử một lần trên bản sao.

Không gửi .venv hoặc cache như dependencies; không đưa khóa truy cập, mật khẩu cá nhân vào gói nộp.
