# Quy tắc cho AI hỗ trợ project

## 1. Đọc và xác định nhiệm vụ

- Đọc README.md, docs/progress.md và tài liệu liên quan đến nhiệm vụ.
- Kiểm tra code hiện có trước khi tạo module, hàm hoặc schema mới.
- Nêu ngắn gọn mục tiêu, file dự kiến sửa, tiêu chí kiểm tra.
- Nếu không truy cập được file, nói rõ và xin nội dung; không giả vờ đã đọc.
- Không cần hỏi lại lựa chọn kỹ thuật đã có trong tài liệu, trừ khi mâu thuẫn với chỉ dẫn mới hoặc môi trường thực tế.

## 2. Các điều kiện phải giữ

- Đây là truy hồi ảnh theo nội dung, không phải chỉ dự đoán nhãn loài.
- Không lọc ứng viên theo loài dự đoán trước khi xếp hạng mặc định.
- Gallery nghiệm thu phải có ít nhất 500 ảnh hợp lệ; query đánh giá không lấy từ gallery.
- Trả về 5 ảnh duy nhất khi gallery hợp lệ có ít nhất 5 ảnh.
- Dùng chung pipeline tiền xử lý và cấu hình cho gallery/query.
- Không so sánh vector khác config_id, khác số chiều hoặc khác phiên bản tiền xử lý.
- HSV=128, HOG=1764, LBP=160 theo baseline-v1; thay đổi phải tạo cấu hình mới.
- Điểm tương đồng không phải xác suất cùng loài và không phải độ chính xác mô hình.
- Không tự thêm huấn luyện CNN, nhận dạng cá thể, đăng nhập, microservice hoặc triển khai cloud vào phạm vi bắt buộc.

## 3. Tổ chức code

- Giao diện gọi service, không tự viết SQL và không tính đặc trưng riêng.
- SQL nằm trong repository; luôn dùng tham số cho dữ liệu đầu vào.
- Similarity là hàm tính toán không có tác dụng phụ.
- Cấu hình thuật toán đi qua config; tránh magic number rải rác.
- Lưu đường dẫn tương đối với thư mục data, không hard-code đường dẫn máy cá nhân.
- Không nuốt ngoại lệ bằng except chung rồi trả kết quả thành công.
- Dữ liệu lỗi phải có image_id/đường dẫn và lý do để sửa lại.
- Không sửa công thức chỉ để vượt test; tìm nguyên nhân mâu thuẫn trước.

## 4. Quy trình mỗi nhiệm vụ

1. Đọc hợp đồng và chỗ gọi hàm bị tác động.
2. Thực hiện một nhiệm vụ nhỏ có tiêu chí nghiệm thu rõ.
3. Kiểm tra phù hợp với rủi ro: vector số, ràng buộc CSDL, top-k, luồng tích hợp.
4. Xem diff; không kèm sửa đổi không liên quan.
5. Cập nhật progress với kết quả thật và lỗi còn lại.
6. Nếu được yêu cầu commit, chỉ commit các file thuộc nhiệm vụ.

Không cần tạo test hình thức cho sửa lỗi chính tả tài liệu. Không chạy đi chạy lại bộ kiểm tra không liên quan khi không có lý do.

## 5. Quản lý thay đổi

- Đổi schema: có migration, xem ảnh hưởng dữ liệu cũ, kiểm tra trên bản sao.
- Đổi đặc trưng: tạo config mới, tính lại vector, không ghi đè ngầm config cũ.
- Đổi hợp đồng: cập nhật contracts và các bên gọi trong cùng nhiệm vụ.
- Không tự xóa ảnh gốc, CSDL, lịch sử Git hoặc thay đổi chưa commit của người khác.
- Chỉ reset/xóa dữ liệu khi người dùng đã yêu cầu rõ phạm vi.
- Giữ một bản CSDL demo có thể khôi phục trước thử nghiệm nhập dữ liệu lớn.

## 6. Bàn giao cuối lượt

Nêu: đã thay đổi gì; kiểm tra nào đã chạy; kết quả; phần chưa kiểm tra; bước tiếp theo. Không ghi 'đã hoàn thành' cho phần chỉ có thiết kế hoặc code chưa chạy. Không tự tạo số liệu thực nghiệm, nguồn ảnh, thời gian chạy hoặc mức chất lượng.

Tài liệu nguồn: requirements giữ yêu cầu; features giữ thuật toán; database giữ schema; contracts giữ giao tiếp; progress giữ trạng thái. Không chép đầy đủ cùng một nội dung vào nhiều file.
