# Đặc trưng và thuật toán truy hồi

## 1. Cấu hình baseline-v1

Đầu vào chung: RGB uint8 128×128 từ preprocess-v1. Bundle là bộ ba config_id cụ thể (HSV, HOG, LBP); không phải 'lấy vector mới nhất bất kỳ'. Lưu versions thư viện trong parameters khi chạy thật.

| Đặc trưng | Cấu hình | Số chiều | Chuẩn hóa cuối |
| --- | --- | ---: | --- |
| HSV | Histogram chung H×S×V, bins 8×4×4 | 128 | L1 toàn vector |
| HOG | 9 orientations, cell 16×16, block 2×2, stride một cell, L2-Hys | 1764 | L2 toàn vector |
| LBP | P=8, R=1, uniform; grid 4×4 | 160 | L1 từng vùng rồi L1 toàn vector |

Mỗi vector lưu JSON array số thực hữu hạn. Không làm tròn trước lưu/tính điểm. Khi đọc đưa về NumPy; sai số round-trip kiểm tra ≤1e-6.

## 2. HSV

Dùng skimage.color.rgb2hsv sau khi chuyển RGB sang float [0,1]. H, S, V có miền [0,1]. Tính histogramdd với ranges [(0,1),(0,1),(0,1)], bins (8,4,4). Quy định bin cuối bao gồm biên phải 1.0. Flatten theo C-order để chỉ số luôn cùng nghĩa.

Đặt n_i là số pixel trong bin i, N=16384:

$$h_i=n_i/N,\quad h_i\ge0,\quad \sum_i h_i=1.$$

Histogram giữ phân bố màu nhưng không giữ vị trí màu. Ví dụ màu cam/đen có thể gần nhau dù hình dạng mặt khác. Nền ảnh chiếm nhiều sẽ làm sai ý nghĩa, vì vậy cần crop tốt.

Minh họa: hiển thị histogram 128 phần tử hoặc các biên tổng hợp theo H/S/V; ghi rõ biểu đồ marginal không thay thế vector histogram chung.

## 3. HOG

Chuyển RGB bằng rgb2gray, giữ float [0,1]. Gọi HOG với orientations=9, pixels_per_cell=(16,16), cells_per_block=(2,2), block_norm='L2-Hys', transform_sqrt=False, feature_vector=True. visualization chỉ phục vụ hiển thị.

Gradient đo thay đổi cường độ theo phương ngang/dọc; mỗi ô gom độ lớn gradient theo hướng. Chuẩn hóa khối giảm ảnh hưởng cường độ cục bộ. Với cấu hình trên: 8×8 ô → 7×7 khối → 7×7×2×2×9=1764 chiều.

Sau chuẩn hóa nội bộ HOG, chuẩn hóa toàn vector:

$$\hat v=v/\|v\|_2\quad\text{khi }\|v\|_2>\varepsilon.$$

Nếu chuẩn ≤1e-12, giữ vector zero và báo cờ zero_gradient. Không chia cho zero. Ảnh gallery mặt thật có đặc trưng zero cần được rà soát chất lượng.

HOG không xuất nhãn 'mõm dài' hoặc 'tai nhọn'; nó mô tả phân bố cạnh liên quan hình dạng. Căn chỉnh lệch, xoay đầu và nền cạnh mạnh có thể làm điểm kém.

## 4. LBP

Tạo grayscale uint8 bằng làm tròn rgb2gray(RGB)×255. Dùng local_binary_pattern(gray_uint8, P=8, R=1, method='uniform'). Giữ quy tắc biên mặc định của triển khai đã khóa phiên bản.

So sánh lân cận với tâm để có mã cục bộ. Với uniform P=8, lập 10 bin mã 0..9 bằng edges -0.5,0.5,...,9.5. Chia ảnh thành 4×4 vùng, mỗi vùng 32×32; duyệt vùng theo hàng trước, cột sau.

Mỗi vùng tạo histogram và chuẩn hóa L1. Ghép 16 histogram theo thứ tự cố định rồi chia tổng để cả vector có tổng 1. Như vậy từng vùng có tổng 1/16. Số chiều 16×10=160.

Việc giữ histogram từng vùng cho phép so sánh kết cấu tại vị trí tương ứng. LBP vẫn nhạy với độ nét, noise và vị trí mặt; không đảm bảo nhận dạng hoa văn chính xác trong mọi ảnh.

## 5. Điểm thành phần và tổng hợp

HSV và LBP dùng histogram intersection:

$$S_{hist}(a,b)=\sum_i\min(a_i,b_i).$$

HOG dùng cosine:

$$S_{hog}(a,b)=\frac{a\cdot b}{\|a\|_2\|b\|_2}.$$

Nếu một trong hai HOG là zero, quy ước S_hog=0 và lưu warning; đây là chính sách dự án, không phải cosine đã được định nghĩa tại zero. Những vector khác phải không âm; clip sai số rất nhỏ của điểm về [0,1], không dùng clip để che vector sai.

$$S=w_cS_{HSV}+w_hS_{HOG}+w_tS_{LBP},\quad w_i\ge0,\quad\sum_iw_i=1.$$

Mặc định mỗi trọng số bằng 1/3. Chấp nhận bộ không âm có tổng dương và chuẩn hóa một lần tại service; trả về trọng số hiệu lực trong kết quả. Nếu cả ba bằng 0, báo INVALID_WEIGHTS.

Các điểm cùng miền [0,1] không đảm bảo có phân bố thống kê giống nhau; vì vậy cần thử trọng số trên validation. Không tự nhận điểm cao là xác suất đúng loài.

## 6. Thuật toán

```text
validate query and weights
preprocess query using preprocess-v1
extract vectors using exact bundle configs
load approved active gallery with all three exact configs
validate dimensions, finiteness and normalization
if valid candidate count < 5: raise INSUFFICIENT_GALLERY
for each candidate:
    compute color, shape, texture scores
    total = weighted sum
sort by (-total, image_id)
select first 5 unique image IDs
persist query configuration and scores atomically
return results, timings, warnings, visualizations
```

Trong tìm kiếm bình thường, ảnh người dùng gửi trùng gallery có thể trả lại chính ảnh đó. Trong đánh giá, query đã tách biệt; nếu kiểm tra nội bộ bằng ảnh gallery phải loại self-match và ghi rõ chế độ, không dùng kết quả đó làm đánh giá chính.

## 7. Thống kê đặc trưng

Trên N ảnh, với chiều j:

$$\mu_j=\frac1N\sum_{n=1}^{N}x_{nj},\quad \sigma_j=\sqrt{\frac1N\sum_{n=1}^{N}(x_{nj}-\mu_j)^2}.$$

Dùng độ lệch chuẩn quần thể (ddof=0), ghi rõ trong báo cáo. Xuất mỗi chiều: min, max, mean, std; thêm norm mỗi ảnh và tỉ lệ vector zero. Có thể tổng hợp theo loài nhưng không đưa nhãn loài vào điểm tìm kiếm.

So sánh phân bố điểm giữa cặp cùng loài/khác loài là một phân tích phụ, không phải bằng chứng rằng cùng loài luôn giống thị giác.

## 8. Nguồn kỹ thuật và giới hạn

- HOG: https://scikit-image.org/docs/stable/auto_examples/features_detection/plot_hog.html
- HOG/LBP API: https://scikit-image.org/docs/stable/api/skimage.feature.html
- Chuyển màu: https://scikit-image.org/docs/stable/api/skimage.color.html

Đây là nguồn để tra cứu triển khai. Những số chiều trong tài liệu được tính từ cấu hình dự án, không lấy mặc định thư viện. Khi code, kiểm tra API của phiên bản đã cài và ghi phiên bản thật; không tự nâng dependency khi chưa có lý do.
