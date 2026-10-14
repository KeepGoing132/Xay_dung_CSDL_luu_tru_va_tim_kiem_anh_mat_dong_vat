# Đặc trưng và thuật toán truy hồi

## Cấu hình cải tiến: refined512-v1

Dùng cùng RGB 512×512/preprocess-512-v1; config và CSDL riêng. Sáu nhóm gồm HSV 128, HOG 9864, LBP 864, Spatial HSV 512, Color Moments 36, GLCM 40; tổng **11444 chiều**. Không thay công thức hoặc vector của expanded/native/baseline. Đây là cải tiến biểu diễn và hiệu chỉnh thang điểm; chưa khẳng định chất lượng thị giác cao hơn khi chưa có đánh giá độc lập.

### Trọng số theo vị trí

Với tọa độ tâm pixel chuẩn hóa x,y trong [0,1], đặt `r=sqrt(((x-.5)/.48)^2+((y-.5)/.5)^2)` và `a=.15+.85*(1+cos(pi*min(r,1)))/2`. Mọi pixel có trọng số từ .15 đến 1: ưu tiên giữa ảnh nhưng giữ đóng góp của tai và vùng rìa. Đây là giả định mặt đã ở giữa, **không phải mask phát hiện mặt hoặc tách nền**. Query lệch mặt cần dùng crop. Không tô đen RGB trước tính gradient vì sẽ sinh cạnh giả.

| Nhóm | Cách trích xuất mới |
| --- | --- |
| HSV | Histogram 8×4×4 có trọng số a, chuẩn hóa tổng 1 |
| HOG | Hai mức cell 32×32 và 64×64, block 2×2, 9 hướng, L2-Hys. Nhân từng block với căn bậc hai của trung bình a trong block; chuẩn L2 mỗi mức, nhân sqrt(.5), ghép rồi L2. Số chiều 8100+1764=9864 |
| LBP | Ba mức uniform (P,R)=(8,1),(16,2),(24,3), mỗi mức grid 4×4. Histogram có trọng số a; chuẩn L1 toàn bộ 16 vùng của từng mức, ghép chia 3. Số chiều 16×(10+18+26)=864 |
| Spatial HSV | Grid 2×2, histogram có trọng số theo tọa độ toàn ảnh; ghép rồi L1 toàn vector |
| Color Moments | Grid 2×2 RGB/255; mean, std và moment bậc 3 có cùng công thức expanded nhưng dùng trung bình có trọng số a; vẫn ánh xạ moment thứ 3 sang [0,1] |
| GLCM | 32 mức xám, khoảng cách 2/6, góc 0/45/90/135 độ. Cặp pixel đóng góp sqrt(a1×a2), offset lấy rint(d×sin/cos); symmetric và chuẩn tổng 1. Giữ contrast, dissimilarity, homogeneity, energy, correlation; bỏ ASM vì energy=sqrt(ASM). Chuẩn miền như expanded; 5×2×4=40 chiều |

### Hiệu chỉnh không dùng nhãn

`scripts/prepare_refined_profile.py` chỉ fit trên ảnh **gallery approved**, sắp theo đường dẫn, tối thiểu 500 ảnh khi chạy CLI. Không dùng nhãn, validation/test hoặc các kết quả chấm thị giác để fit. Tệp bất biến `data/calibration/refined512-v1/gallery.json` lưu nguồn/checksum/crop, dấu tham số thuật toán, versions thư viện, các thang đo và thống kê khoảng cách. Script chạy lại chỉ tái sử dụng nếu nguồn/crop/cấu hình vẫn khớp; không tự ghi đè calibration.

- HSV/Spatial HSV/LBP: khoảng cách `d=1-intersection`.
- HOG: `d=1-cosine`; vector zero vẫn cho điểm 0 kèm warning.
- Moments/GLCM: thang từng chiều `s_j=max(Q75_j-Q25_j,.02)` trên gallery. Khoảng cách `d=mean(min(abs(x_j-y_j)/s_j,5))`. Việc này giảm chênh lệch thang thực tế giữa các thống kê, có sàn để tránh khuếch đại chiều gần hằng.
- Lấy 4096 cặp gallery khác nhau, không lặp cặp, seed 20261013; mỗi nhóm dùng `t=max(median(d),.01)`. Điểm `S=exp(-ln(2)*d/t)`. Nếu không chạm sàn thì khoảng cách trung vị tương ứng điểm .5. Hiệu chỉnh này cân bằng thang đo, không tạo xác suất liên quan và không đảm bảo phân biệt đúng mọi cặp ảnh.
- Trọng số khởi đầu cân bằng ba khía cạnh: màu 1/3 (HSV, Spatial HSV, Moments mỗi nhóm 1/9), hình dạng HOG 1/3, kết cấu 1/3 (LBP/GLCM mỗi nhóm 1/6). Không gọi đây là trọng số tối ưu. Điểm cuối vẫn là tổng có trọng số; không lọc ứng viên bằng loài.

Runtime bắt buộc calibration hợp lệ, chép toàn bộ metric và hash calibration vào config bất biến trong SQLite. Thay file không khớp config đã đăng ký sẽ báo CONFIG_CONFLICT. Khi thêm gallery, có thể dùng thang đã đóng băng; muốn fit lại phải tạo profile/version mới. Cả query và gallery dùng cùng dấu tham số đầy đủ, không chỉ so ID số.

Minh họa UI: bản đồ a; HOG kết hợp hai mức có ưu tiên vùng; LBP hiển thị mức R=1 và ghi rõ vector dùng cả ba mức. Các preview gọi đúng tham số của bundle đang tìm.

## Cấu hình mở rộng: expanded512-v1

Profile mới dùng cùng `preprocess-512-v1` (RGB 512×512) và sáu config có tên riêng, không sửa baseline/native512. Tổng **35480 chiều**: HSV 128, HOG 34596, LBP 160, Spatial HSV 512, Color Moments 36 và GLCM 48. HSV/HOG/LBP giữ nguyên công thức bên dưới; ba bộ bổ sung được định nghĩa như sau.

| Bộ bổ sung | Cách tính và thứ tự vector | Chuẩn hóa / so sánh |
| --- | --- | --- |
| Spatial HSV | Chia ảnh 2×2 theo hàng trước; mỗi vùng tính histogram HSV 8×4×4 | L1 từng vùng, ghép rồi chia 4; tổng 1; histogram intersection |
| Color Moments | 2×2 vùng, RGB/255; mỗi kênh lấy mean, std quần thể và căn bậc ba có dấu của moment trung tâm bậc 3; thứ tự vùng → kênh → thống kê | Moment thứ 3 được ánh xạ `(cbrt(mean((x-mean)^3))+1)/2`; cả 36 giá trị thuộc [0,1] |
| GLCM | Grayscale uint8 theo quy tắc LBP, lượng tử `gray*32//256`; khoảng cách [1,3], góc [0,45,90,135] độ; symmetric=True, normed=True | Mỗi thuộc tính flatten theo khoảng cách → góc; sáu thuộc tính theo thứ tự contrast, dissimilarity, homogeneity, ASM, energy, correlation |

GLCM có 6×2×4=48 chiều. Contrast chia 31², dissimilarity chia 31, correlation ánh xạ `(r+1)/2`; các thuộc tính còn lại giữ giá trị trong [0,1]. Ảnh đồng nhất dùng quy ước correlation của scikit-image (=1). Color Moments/GLCM dùng `exp(-mean(abs(a-b))/0.1)`; scale được lưu trong config. Đây là thang điểm của dự án, không phải xác suất. Từng bộ có thể tắt bằng trọng số 0; tổng trọng số hiệu lực luôn bằng 1.

Spatial HSV giữ thông tin vị trí màu mà HSV toàn ảnh bỏ qua; Color Moments bổ sung thống kê màu không phụ thuộc ranh giới histogram; GLCM mô tả quan hệ mức xám ở các hướng/khoảng cách. Cả ba vẫn nhạy với crop, vị trí mặt, nền và ánh sáng; không khẳng định thêm chiều sẽ tăng chất lượng. Trọng số khởi đầu sáu nhóm là 0.1/0.3/0.2/0.15/0.1/0.15, phải phân biệt với trọng số chọn trên validation. Kết quả thực nghiệm được quản lý tại testing-evaluation/progress.

Triển khai GLCM đối chiếu [API chính thức scikit-image](https://scikit-image.org/docs/stable/api/skimage.feature.html#skimage.feature.graycomatrix) và [ví dụ GLCM](https://scikit-image.org/docs/stable/auto_examples/features_detection/plot_glcm.html). Tham số và implementation_version được lưu trong config mới; versions thư viện được ghi trong lịch sử tìm kiếm và experiment JSON. Thống kê min/max/mean/std(ddof=0) từng chiều được xuất bằng `scripts/export_statistics.py` theo profile.

## Các cấu hình 512×512 ba nhóm được giữ lại

Cấu hình `native512-v1` dùng `preprocess-512-v1`; `background512-white-v1` dùng `preprocess-bg-white-512-v1`. Cả hai tính trên RGB uint8 512×512. Profile tách nền ghép alpha lên nền trắng trước khi crop; query và gallery dùng cùng cấu hình. Baseline 128 bên dưới được giữ để đọc lịch sử, không ghi đè tham số hoặc vector cũ.

| Đặc trưng | Số chiều ở 512 | Tham số |
| --- | ---: | --- |
| HSV | 128 | Histogram 8×4×4; N=512×512=262144 pixel |
| HOG | 34596 | 9 hướng, cell 16×16, block 2×2; 32×32 cell → 31×31 block → 31×31×36 |
| LBP | 160 | P=8, R=1, uniform; grid 4×4, mỗi vùng 128×128 |

Tổng 34884 chiều/ảnh. Chuẩn hóa và công thức điểm giữ như bên dưới. Mỗi profile có ba config mới, `input_size=[512,512]` trong parameters và preprocess riêng. Similarity kiểm tra cả config_ids, số chiều và preprocess_version; hai SQLite có ID số trùng nhau vẫn không được trộn vector giữa các profile. Tăng kích thước không tự chứng minh chất lượng truy hồi tốt hơn; cần đánh giá lại trên validation/test.

## 1. Cấu hình baseline-v1 (128, giữ tương thích)

Đầu vào chung: RGB uint8 128×128 từ preprocess-v1. Bundle là bộ ba config_id cụ thể (HSV, HOG, LBP); không phải 'lấy vector mới nhất bất kỳ'. Lưu versions thư viện trong parameters khi chạy thật.

| Đặc trưng | Cấu hình | Số chiều | Chuẩn hóa cuối |
| --- | --- | ---: | --- |
| HSV | Histogram chung H×S×V, bins 8×4×4 | 128 | L1 toàn vector |
| HOG | 9 orientations, cell 16×16, block 2×2, stride một cell, L2-Hys | 1764 | L2 toàn vector |
| LBP | P=8, R=1, uniform; grid 4×4 | 160 | L1 từng vùng rồi L1 toàn vector |

Mỗi vector lưu JSON array số thực hữu hạn. Không làm tròn trước lưu/tính điểm. Khi đọc đưa về NumPy; sai số round-trip kiểm tra ≤1e-6.

## 2. HSV

Profile tùy chọn `background-white-v1` dùng cùng công thức và số chiều, nhưng config mới `hsv-bg-white-v1`, `hog-bg-white-v1`, `lbp-bg-white-v1` gắn với `preprocess-bg-white-v1`. Không ghi đè config baseline. Đầu vào là PNG đã tách nền; alpha ghép trắng trước crop/resize. Import và query cùng profile; khác config_id/preprocess không được so sánh.

Dùng skimage.color.rgb2hsv sau khi chuyển RGB sang float [0,1]. H, S, V có miền [0,1]. Tính histogramdd với ranges [(0,1),(0,1),(0,1)], bins (8,4,4). Quy định bin cuối bao gồm biên phải 1.0. Flatten theo C-order để chỉ số luôn cùng nghĩa.

Đặt n_i là số pixel trong bin i; N=16384 ở baseline 128, N=262144 ở profile 512:

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

So sánh lân cận với tâm để có mã cục bộ. Với uniform P=8, lập 10 bin mã 0..9 bằng edges -0.5,0.5,...,9.5. Chia ảnh thành 4×4 vùng, mỗi vùng 32×32 ở baseline 128 hoặc 128×128 ở profile 512; duyệt vùng theo hàng trước, cột sau, phủ toàn bộ ảnh.

Mỗi vùng tạo histogram và chuẩn hóa L1. Ghép 16 histogram theo thứ tự cố định rồi chia tổng để cả vector có tổng 1. Như vậy từng vùng có tổng 1/16. Số chiều 16×10=160.

Việc giữ histogram từng vùng cho phép so sánh kết cấu tại vị trí tương ứng. LBP vẫn nhạy với độ nét, noise và vị trí mặt; không đảm bảo nhận dạng hoa văn chính xác trong mọi ảnh.

## 5. Điểm thành phần và tổng hợp

HSV và LBP dùng histogram intersection:

$$S_{hist}(a,b)=\sum_i\min(a_i,b_i).$$

HOG dùng cosine:

$$S_{hog}(a,b)=\frac{a\cdot b}{\|a\|_2\|b\|_2}.$$

Nếu một trong hai HOG là zero, quy ước S_hog=0 và lưu warning; đây là chính sách dự án, không phải cosine đã được định nghĩa tại zero. Những vector khác phải không âm; clip sai số rất nhỏ của điểm về [0,1], không dùng clip để che vector sai.

$$S=w_cS_{HSV}+w_hS_{HOG}+w_tS_{LBP},\quad w_i\ge0,\quad\sum_iw_i=1.$$

Giao diện mặc định HSV/HOG/LBP = 0,1/0,45/0,45. Chấp nhận bộ không âm có tổng dương và chuẩn hóa một lần tại service; trả về trọng số hiệu lực trong kết quả. Nếu cả ba bằng 0, báo INVALID_WEIGHTS.

Các điểm cùng miền [0,1] không đảm bảo có phân bố thống kê giống nhau; vì vậy cần thử trọng số trên validation. Không tự nhận điểm cao là xác suất đúng loài.

## 6. Thuật toán

```text
validate query and weights
preprocess query using the selected profile version and input size
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
