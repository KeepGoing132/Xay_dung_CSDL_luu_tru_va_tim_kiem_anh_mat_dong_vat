# Prompt làm việc với AI theo từng nhiệm vụ

Các khối dưới dùng để copy vào công cụ AI có quyền đọc project. Nếu chỉ dùng chat thông thường, đính kèm các file liên quan. Tên file trong prompt không tự cấp quyền truy cập. Không yêu cầu AI 'nhớ vĩnh viễn'; cập nhật tài liệu và Git sau mỗi mốc.

## 1. Bắt đầu project

```text
Tôi đang làm bài tập CSDL tìm ảnh mặt động vật.
Đọc README.md, AGENTS.md, docs/requirements.md, docs/progress.md
và docs/implementation-plan.md.

Thực hiện T01. Trước khi tạo file, kiểm tra thư mục hiện tại.
Nêu ngắn cấu trúc và các dependency cần dùng; kiểm tra phiên bản
thực tế cài được, ghi lại phiên bản đã dùng.
Tạo khung tối thiểu để làm tiếp preprocessing/repository.
Không đánh dấu module chưa có là đã hoàn thành.

Kết thúc: kiểm tra môi trường phù hợp, cập nhật progress và
nêu các lệnh đã thực sự chạy cùng kết quả.
```

## 2. Tiền xử lý và dữ liệu

```text
Đọc AGENTS.md, progress.md, dataset.md và contracts.md trong docs.
Thực hiện T02 trên các ảnh thật tôi đã cung cấp.
Nếu chưa có ảnh, triển khai và kiểm tra pipeline bằng ảnh fixture,
nhưng báo rõ chưa thu thập dữ liệu dự án.

Giữ đúng EXIF → alpha/RGB → crop vuông → resize 128×128.
Crop tính trên ảnh sau EXIF; không âm thầm kẹp crop sai vào biên.
Lưu thông tin crop và checksum; tạo preview để kiểm tra mặt.
Kiểm tra RGB, grayscale, alpha, ảnh hỏng và crop ngoài biên.
Không tự coi center crop là bộ phát hiện mặt động vật.
```

## 3. CSDL

```text
Đọc AGENTS.md, docs/database.md và docs/contracts.md.
Thực hiện T03: migration SQLite và repository nền.
Đối chiếu schema trong tài liệu trước khi tạo bảng.
Bật foreign_keys cho từng connection, dùng SQL tham số hóa.
Kiểm tra PK/FK/UNIQUE, nhập lặp và lưu/đọc JSON vector.
Vector sai chiều hoặc NaN/Inf phải bị từ chối.
Không reset hoặc xóa CSDL hiện có để né lỗi migration.
Nếu thay schema là cần thiết, nêu lý do và cập nhật tài liệu.
```

## 4. Trích xuất đặc trưng

```text
Đọc docs/features.md, docs/contracts.md và code preprocessing.
Thực hiện [T04 hoặc phần cụ thể của T06].
Sử dụng đúng tham số đã chốt, không lấy default thư viện.
Giữ HSV=128, HOG=1764, LBP=160 trong baseline-v1.
Tách hàm trích xuất khỏi UI và repository.
Kiểm tra shape, finite, chuẩn hóa và zero-gradient.
Kèm một ảnh minh họa thật nếu đã có dữ liệu.
Nêu rõ tests nào dùng ảnh tổng hợp, tests nào dùng ảnh dự án.
```

## 5. Tìm kiếm và tích hợp

```text
Đọc contracts.md, features.md, architecture.md và code repository.
Triển khai search service theo baseline-v1.
Query không cần nhãn loài; ứng viên là toàn gallery approved/active
có đủ đúng ba config.
Trả đúng 5 ID duy nhất, sort (-total_score, image_id).
Kiểm tra weights, zero HOG, thiếu gallery, vector khác config.
Lưu query+results trong một transaction; không làm tròn điểm trước lưu.
Chạy test tích hợp và nêu số ảnh thực sự dùng trong test.
```

## 6. Rà soát độc lập sau một chức năng

```text
Rà soát thay đổi của [task] theo requirements và contracts.
Chưa sửa code ở lượt này.
Tìm lỗi có thể tái hiện: sai input/output, sai config, dữ liệu lỗi,
sai sort, rò rỉ query test vào gallery, transaction dở dang.
Mỗi phát hiện phải có vị trí, tình huống và ảnh hưởng.
Không coi nhận xét phong cách là lỗi chức năng.
Không kết luận 'không có lỗi' chỉ vì code trông hợp lý;
nêu phạm vi đã kiểm tra và phần chưa chạy.
```

## 7. Sửa lỗi có bằng chứng

```text
Nhiệm vụ đang làm: [ID].
Lệnh/thao tác gây lỗi: [...].
Mong đợi: [...].
Thực tế: [...].
Log nguyên văn: [...].
File liên quan: [...].

Xác định nguyên nhân dựa trên code và log.
Nếu chưa đủ bằng chứng, nêu kiểm tra tiếp theo cần làm.
Sửa trong phạm vi cần thiết, chạy lại đúng tình huống lỗi
và kiểm tra chức năng chịu ảnh hưởng.
Không tự sửa công thức/schema để né lỗi chưa hiểu.
```

## 8. Đánh giá

```text
Đọc testing-evaluation.md và manifest gallery/validation/test.
Kiểm tra trùng group trước khi đánh giá.
Thực hiện các run HSV, HOG, LBP, kết hợp trên cùng candidate set.
Chọn trọng số bằng validation; không chọn bằng test.
Nếu chưa có judgments, tạo cấu trúc để gán nhãn và báo thiếu,
không tự coi điểm similarity là relevance đúng.
Xuất per-query results, metrics, thời gian, environment và failures.
Không bịa số liệu khi code chưa chạy hoặc dữ liệu chưa có.
```

## 9. Kết thúc chat và mở chat mới

```text
Hãy cập nhật docs/progress.md theo trạng thái thực tế:
đã sửa gì, lệnh nào chạy, kết quả, phần chưa kiểm tra, lỗi còn lại,
quyết định mới và task tiếp theo.
Chỉ cập nhật tài liệu thiết kế nếu hành vi/thiết kế thực sự thay đổi.
Nếu được yêu cầu commit, xem diff và chỉ commit phần của nhiệm vụ.
```

Prompt chat mới:

```text
Đọc AGENTS.md, README.md và docs/progress.md.
Nhiệm vụ lần này: [Txx và phạm vi nhỏ].
Đọc tài liệu, implementation và caller liên quan trước khi sửa.
Tóm tắt ngắn các ràng buộc cần giữ, rồi thực hiện nhiệm vụ.
Kết thúc bằng kiểm tra phù hợp và cập nhật progress.
```

## 10. Khi model yếu bị lặp lỗi

Dừng mở rộng chức năng. Yêu cầu liệt kê đã thử gì và kết quả, tạo tình huống lỗi tối thiểu, kiểm tra đầu vào/đầu ra từng module. Chỉ đổi một giả thuyết mỗi lần sửa. Nếu phải chuyển chat, mang theo log và giả thuyết đã loại để tránh lặp lại.

Giữ yêu cầu ngắn trong mỗi prompt; dùng file làm nguồn tham chiếu chi tiết. Không đưa hàng chục nhiệm vụ phụ vào một lượt hoặc bắt AI tự chọn lại kiến trúc ở mọi chat.
