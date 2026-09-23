# Bộ dữ liệu và tiền xử lý

## 1. Quy mô và chọn nguồn

Gallery tối thiểu 500 ảnh đạt yêu cầu, không tính query ngoài gallery để bù số lượng. Có thể chọn khoảng 5 nhóm động vật với phân bố tương đối cân bằng nhưng không bắt buộc 5 loài. Thu thập dư để loại ảnh nghiêng, nhiều mặt, thiếu đầu hoặc trùng.

Chưa xác định bộ dữ liệu nguồn cụ thể trong gói tài liệu này. Khi chọn nguồn phải kiểm tra thật: quyền truy cập, điều kiện sử dụng, ảnh có đủ chính diện không, số lượng sau lọc. Không ghi tên một bộ dữ liệu vào báo cáo như đã sử dụng nếu chưa tải và kiểm tra.

Lưu URL/trích dẫn nguồn, tác giả hoặc đơn vị cung cấp nếu có, ngày lấy và ghi chú giấy phép. Không tự nhận ảnh sưu tầm là ảnh nhóm tự chụp.

## 2. Manifest đầu vào

CSV UTF-8 dự kiến:

```csv
relative_path,species_name,source_url,license_note,split,group_id,crop_x,crop_y,crop_size,review_note
original/cat_001.jpg,cat,,,gallery,cat_source_001,20,10,240,can kiem tra bang anh that
```

Dòng trên minh họa cú pháp, không phải ảnh đã có. Tọa độ crop tính trên ảnh sau khi sửa EXIF orientation, gốc ở góc trái trên. crop_size là cạnh vùng vuông; vùng phải nằm hoàn toàn trong ảnh. Nếu không khai báo crop, hệ thống dùng center square crop và bắt buộc xem trước.

group_id gom các bản gần trùng, ảnh liên tiếp cùng cảnh hoặc cùng nguồn gốc. Không để một group xuất hiện ở cả gallery và query đánh giá. Nếu biết cá thể, cân nhắc tách theo cá thể để tránh kết quả quá dễ.

## 3. Quy tắc duyệt ảnh

| Tiêu chí | Đạt | Không đạt |
| --- | --- | --- |
| Số mặt | Một mặt chính | Nhiều mặt không tách được |
| Góc nhìn | Tương đối chính diện, thấy hai mắt | Nghiêng mạnh, quay lưng |
| Vị trí | Mặt gần tâm sau crop | Mặt nằm sát mép |
| Phạm vi | Tai/cằm giữ tương đối nhất quán | Cắt mất phần quan trọng tùy tiện |
| Tỉ lệ | Khuôn mặt chiếm phần lớn crop, đồng đều tương đối | Ảnh toàn thân xen với ảnh sát mặt |
| Chất lượng | Mắt/mũi và hoa văn nhận ra được | Mờ nặng, quá tối, che khuất nhiều |
| Trùng | Nội dung riêng biệt | Bản đổi tên, resize hoặc crop gần như giống hệt |

Có thể đề xuất khoảng chiếm khung, ví dụ 65–90% theo kích thước hộp mặt, nhưng phải định nghĩa hộp mặt nhất quán và kiểm tra thật; đây không phải ngưỡng của đề. Không dùng ngưỡng này như phép chứng minh tự động mọi ảnh đạt chuẩn.

## 4. Pipeline preprocess-v1

1. Giải mã ảnh; lỗi thì từ chối và ghi lý do.
2. Sửa hướng EXIF trước khi áp dụng tọa độ.
3. Ảnh có alpha: ghép trên nền trắng trước chuyển RGB. Ảnh grayscale: nhân thành RGB.
4. Cắt vùng vuông theo manifest hoặc vùng chọn của người dùng; mặc định center square crop.
5. Resize 128×128 với một phương pháp cố định, đề xuất bilinear.
6. Xuất RGB uint8, miền 0..255; lưu ảnh PNG đã xử lý để không thêm nén mất dữ liệu.
7. Lưu crop, phiên bản tiền xử lý, checksum file gốc và checksum pixel đã xử lý.
8. Mở ảnh xem trước để duyệt chất lượng. Thuật toán center crop không tự đảm bảo tìm đúng mặt.

Không dùng augmentation ngẫu nhiên trong pipeline truy vấn mặc định. Không thay đổi tương phản/khử nền chỉ cho query mà không áp dụng giống gallery.

## 5. Trùng và chia tập

- SHA-256 file gốc phát hiện trùng byte.
- SHA-256 RGB pixel chuẩn hóa phát hiện nội dung chuẩn hóa giống hệt.
- Các ảnh gần trùng nhưng khác nén/crop cần kiểm tra trực quan hoặc bổ sung perceptual hash; không coi checksum là đủ.
- group_id giúp kiểm soát rò rỉ giữa tập.
- Gallery: ≥500 ảnh; validation: ví dụ 20; test: ví dụ 30; các số sau là đề xuất.
- Query loài chưa có được ghi riêng là unknown-species; nhãn được người làm biết để đánh giá, không đưa vào hàm tìm kiếm.
- Điều chỉnh trọng số trên validation. Khóa cấu hình trước test; không tiếp tục chọn trọng số theo điểm test.

## 6. Thống kê phải xuất

Tổng thu thập; tổng loại và lý do; tổng gallery được duyệt; phân bố loài/split; ảnh chưa có nguồn; ảnh thiếu vector; kích thước ảnh; số group trùng. Tạo contact sheet 20–30 ảnh tiêu biểu để chứng minh căn chỉnh.

Các file đầu ra dự kiến: gallery.csv, validation_queries.csv, test_queries.csv, rejected.csv, dataset_stats.csv. Với biểu đồ thống kê, dùng dữ liệu thật từ manifest/DB, không nhập tay con số để khớp kế hoạch.

## 7. Hoàn thành

- [ ] Ít nhất 500 gallery được duyệt trực quan.
- [ ] File có thật, giải mã được, RGB 128×128 sau xử lý.
- [ ] Không trùng byte; đã duyệt gần trùng.
- [ ] Query test tách biệt theo group.
- [ ] Có nguồn và ghi chú sử dụng.
- [ ] Manifest tái tạo được vùng crop và split.
