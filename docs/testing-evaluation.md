# Kiểm thử và đánh giá

## 1. Hai việc khác nhau

Kiểm thử kỹ thuật trả lời 'hệ thống có làm đúng đặc tả không?'. Đánh giá truy hồi trả lời 'các ảnh trả về có phù hợp về thị giác không?'. Test code pass không chứng minh chất lượng truy hồi cao. Điểm similarity cao cũng không tự chứng minh kết quả đúng.

## 2. Test kỹ thuật tối thiểu

| ID | Tình huống | Kết quả mong đợi |
| --- | --- | --- |
| UT01 | RGB/grayscale/alpha hợp lệ | Cùng output RGB uint8 128×128 |
| UT02 | File hỏng, bytes rỗng | INVALID_IMAGE |
| UT03 | Crop ngoài biên | INVALID_CROP |
| UT04 | HSV ảnh một màu | 128 phần tử, sum≈1, bin màu đúng |
| UT05 | HOG ảnh có cạnh | 1764 phần tử, finite, norm≈1 |
| UT06 | HOG ảnh đồng nhất | Zero theo cấu hình, không NaN; score policy=0 |
| UT07 | LBP | 160 phần tử, sum≈1, mỗi vùng sum≈1/16 |
| UT08 | Vector khác config ID dù cùng shape | CONFIG_MISMATCH |
| UT09 | Trọng số 2,1,1 | Chuẩn hóa thành 0.5,0.25,0.25 |
| UT10 | Trọng số âm/NaN/all-zero | INVALID_WEIGHTS |
| UT11 | Bằng điểm | image_id tăng dần |
| UT12 | Thiếu ứng viên | INSUFFICIENT_GALLERY |
| IT01 | Ghi/đọc vector JSON | Shape và giá trị khớp ≤1e-6 |
| IT02 | Metadata FK không tồn tại | Bị DB từ chối |
| IT03 | Nhập lại checksum gốc | Skipped, số ảnh không tăng |
| IT04 | Lưu kết quả lỗi giữa transaction | Không còn query/results dở dang |
| IT05 | Gallery gồm validation/test | Chỉ split=gallery được so sánh |
| IT06 | Ảnh thiếu vector hoặc file | Bị loại, có rejected reason |
| E2E01 | Query loài chưa có | Vẫn trả 5 ảnh nếu gallery đủ |
| E2E02 | Restart app và mở lịch sử | Cùng ảnh/điểm đã lưu |

## 3. Kiểm tra toán học độc lập

Histogram a=[0.5,0.5], b=[1,0] có intersection=0.5. Hai histogram [0.5,0.5] giống nhau có intersection=1. HOG toy a=[1,0], b=[0,1] có cosine=0; a=b=[1,0] có cosine=1.

Nếu ba điểm là 0.9, 0.8, 0.7 và weights bằng nhau, total=0.8. Đặt expected bằng tính tay, không gọi cùng hàm implementation để tạo expected.

Test toy vector kiểm tra hàm số học riêng, không yêu cầu toy có đủ chiều của FeatureBundle production. Contract cấp bundle vẫn phải kiểm tra dimension thật.

## 4. Chất lượng tập đánh giá

- Chốt gallery có ít nhất 500 ảnh đạt chuẩn.
- Query validation/test tách biệt với gallery và nhau; kiểm tra group và gần trùng.
- Phân bố query theo loài/chất lượng để tránh chỉ chọn ảnh quá dễ.
- Có nhóm unknown-species riêng, không tính cùng loài với gallery là tiêu chuẩn phù hợp của nhóm này.
- Giữ danh sách query cố định khi so sánh phương pháp.

## 5. Định nghĩa relevance trước khi chạy

Hai hướng báo cáo riêng:

1. Same-species@5: số ảnh cùng loài chia 5. Đây là độ trùng nhãn, không phải đánh giá toàn diện độ giống thị giác.
2. Visual P@5: số ảnh được con người đánh giá phù hợp về thị giác chia 5.

Rubric đề xuất cho mỗi cặp query–candidate: hình dạng mặt 0..2; màu 0..2; hoa văn/kết cấu 0..2. 0=khác rõ, 1=giống một phần, 2=giống rõ. Tổng 0..6; quy ước phù hợp khi ≥4. Đây là tiêu chí nhóm tự đề xuất, cần ghi rõ và cố định trước so sánh. Điều chỉnh rubric chỉ bằng validation.

Nếu có thể, hai người gán nhãn độc lập mà không xem điểm hệ thống, sau đó giải quyết bất đồng. Ghi số người thực tế; không tuyên bố đánh giá nhiều người nếu chỉ một người làm.

Để giảm công sức, gom union top 5 từ tất cả phương pháp đang so sánh cho mỗi query, ẩn phương pháp/rank/score rồi gán nhãn. Cách pooling này đủ để chấm top 5 của các phương pháp đã góp pool; không đủ để đo recall toàn gallery hoặc đánh giá phương pháp mới trả ảnh chưa được chấm. Những cặp chưa chấm phải được chấm bổ sung, không mặc định là sai.

## 6. Chỉ số

$$P@5(q)=\frac{\sum_{r=1}^{5}relevant(q,x_r)}{5}.$$

$$MeanP@5=\frac1Q\sum_{q=1}^{Q}P@5(q).$$

Ví dụ minh họa: 3/5 ảnh phù hợp thì P@5=0.6. Không dùng ví dụ này làm kết quả dự án.

Tổng hợp: trung bình trên query thành công, số query thất bại và nguyên nhân. Báo thêm mean trên toàn bộ test với query thất bại tính 0 để không che thất bại. Không tính precision bằng cách chia cho số ảnh ít hơn 5 trong bản chuẩn.

Đo latency bằng đồng hồ đơn điệu độ phân giải cao. Báo cấu hình máy, số ảnh, cache có/không, số lần lặp; phân biệt lần đầu với các lần sau. Báo median và p95 nếu đủ mẫu, kèm số mẫu. Không khẳng định mục tiêu tốc độ đã đạt khi chưa đo.

## 7. Thực nghiệm so sánh

| Run | HSV | HOG | LBP | Mục đích |
| --- | ---: | ---: | ---: | --- |
| A | 1 | 0 | 0 | Baseline màu |
| B | 0 | 1 | 0 | Hình dạng |
| C | 0 | 0 | 1 | Kết cấu |
| D | 1/3 | 1/3 | 1/3 | Kết hợp mặc định |
| E | Chọn trên validation | Chọn trên validation | Chọn trên validation | Kết hợp điều chỉnh |

Dùng cùng tập ứng viên đủ cả ba vectors để so sánh công bằng. Baseline app vẫn tính cả ba để minh họa; nếu đo extractor đơn lẻ thì báo riêng, không so latency khác quy trình như thể cùng điều kiện.

## 8. File kết quả dự kiến

- judgments.csv: query_key,image_id,shape_grade,color_grade,texture_grade,relevant,rater.
- per_query_results.csv: run_id,query_key,rank,image_id,ba điểm,total,relevant.
- metrics.csv: run_id,n_queries,n_failed,mean_p5,mean_all_p5,latency_median_ms.
- experiment.json: bundle IDs, parameters, weights, environment, gallery manifest checksum, query manifest checksum, seed nếu có sampling.
- failures.md: các case sai và giải thích có ảnh minh họa.

## 9. Phân tích lỗi

Chọn ít nhất vài trường hợp đại diện: nền ảnh chi phối màu; cùng màu nhưng khác cấu trúc; ánh sáng mạnh; mặt lệch crop; loài chưa có. So sánh điểm từng nhóm để giải thích; tránh chỉ kết luận 'AI chưa tốt' vì baseline không phải mô hình phân loại học sâu.

Kết luận phải bám số liệu: nếu kết hợp không cải thiện, báo đúng và phân tích; không chọn riêng query thuận lợi để che kết quả.
