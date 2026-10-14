# Kiểm thử và đánh giá

## Đối chiếu refined512-v1 không dùng nhãn

Chạy `scripts/prepare_refined_profile.py` để hiệu chỉnh bằng gallery và nhập CSDL mới. Các test trong `tests/test_refined_features.py` kiểm tra ảnh hưởng vị trí màu, GLCM đếm cặp có trọng số bằng kết quả tính tay, ảnh hằng/zero-gradient, kích thước và chuẩn vector, fit xác định/không dùng nhãn hoặc query, calibration sai, dấu cấu hình, API top-5/history/preview.

`scripts/compare_visual_profiles.py --split validation` và `--split test` đối chiếu trọng số khởi đầu expanded/refined trên cùng gallery. Không chọn trọng số bằng nhãn. Kết quả tại `artifacts/evaluation/refined512-v1/`: HTML xem query và hai hàng top-5; CSV điểm/thời gian từng kết quả; JSON dấu cấu hình, số query và cờ labels_used=false; CSV judgments chưa chấm. Image ID trong CSV so sánh là đường dẫn nguồn để không phụ thuộc ID số của hai CSDL.

Điền shape_grade/color_grade/texture_grade (0,1,2) và rater trong judgments, rồi chạy:

```powershell
.venv/Scripts/python.exe scripts/score_judgments.py --results artifacts/evaluation/refined512-v1/results_validation.csv --judgments artifacts/evaluation/refined512-v1/judgments_validation.csv --output artifacts/evaluation/refined512-v1/visual_validation.json
```

Chưa điền đủ thì script báo lỗi, không tự coi cặp thiếu đánh giá là không giống. Dùng validation để lựa chọn sau khi có chấm thật; giữ test độc lập. Top-5 giống/khác nhãn, median điểm đã hiệu chỉnh hoặc số chiều nhỏ hơn đều không tự chứng minh chất lượng thị giác cao hơn. HTML hiện tên profile nên là công cụ đối chiếu, chưa phải thí nghiệm đánh giá mù.

## Kết quả expanded512-v1 ngày 13/10/2026

Đã chạy thật 50 query validation (15 run) và 50 query test (11 run), cùng 500 ứng viên, không có query thất bại. Trọng số chọn bằng validation: HOG=0.6, Spatial HSV=0.2, GLCM=0.2, các nhóm còn lại=0. Không thay trọng số sau khi xem test.

| Phương pháp | Validation P@5 theo nhãn | Test P@5 theo nhãn |
| --- | ---: | ---: |
| Chỉ HSV | 0.352 | 0.296 |
| Chỉ HOG | 0.532 | 0.604 |
| Chỉ LBP | 0.336 | 0.416 |
| Ba nhóm cũ bằng nhau | 0.420 | 0.356 |
| Chỉ Spatial HSV | 0.332 | 0.280 |
| Chỉ Color Moments | 0.364 | 0.332 |
| Chỉ GLCM | 0.508 | 0.416 |
| Sáu nhóm bằng nhau | 0.436 | 0.400 |
| Sáu nhóm trọng số khởi đầu | 0.468 | 0.452 |
| Tổ hợp chọn trên validation | 0.568 | 0.544 |

Nguồn: `data/evaluation/expanded512-v1/metrics_validation.csv`, `metrics_test.csv`, `per_query_results_*.csv` và `experiment_*.json`. Sáu nhóm giúp mở rộng khả năng phân tích/so sánh; tổ hợp được chọn **không vượt HOG-only trên test** (0.544 so với 0.604). Không dùng kết quả này để khẳng định chất lượng luôn tăng. Chỉ số trên đo trùng nhóm nhãn, không phải độ chính xác phân loại hoặc Visual P@5. Cần chấm pool bằng rubric và phân tích thất bại trước khi kết luận về độ giống thị giác.

## Công cụ mở rộng

`evaluate.py --profile expanded512-v1 --split validation` chạy từng nhóm và các tổ hợp. Test chỉ được chạy sau validation đầy đủ, với selected_weights.json có signature khớp bundle/manifest/gallery. Query phải approved, không trùng group/path/hash byte/pixel với gallery; manifest không có group xuyên split. Công cụ yêu cầu ít nhất 500 ứng viên hợp lệ. Chạy thử `--limit` không chọn lại trọng số. Preset theo validation trên UI chỉ xuất hiện khi signature còn khớp.

Kết quả từng query có sáu điểm trong scores_json; metrics báo P@5 theo nhãn, macro trung bình theo nhóm nhãn, số lỗi và mean_all_known_p5 (query nhãn biết nhưng lỗi tính 0). Unknown-label không bị ép thành cùng loài=0. Latency gồm đọc/preprocess/extract/tính toàn bộ điểm/xếp hạng; điểm thành phần được dùng chung giữa các bộ trọng số, thời gian nạp gallery báo riêng. Không coi đây là latency HTTP hoặc chạy model tách nền.

Experiment JSON giữ hash manifest, fingerprint gallery, danh sách query, config IDs/parameters/dimensions, versions thư viện, môi trường và weights. Pool CSV là hợp các top-5, không chứa rank/score/phương pháp, dành cho gán nhãn người thật. Không tự điền điểm. Sau khi điền shape_grade/color_grade/texture_grade (0..2) và rater:

```powershell
.venv\Scripts\python.exe scripts/score_judgments.py --results data/evaluation/expanded512-v1/per_query_results_test.csv --judgments data/evaluation/expanded512-v1/judgments_pool_test.csv --output data/evaluation/expanded512-v1/visual_metrics_test.json
```

Công cụ từ chối cặp thiếu điểm; nếu có nhiều người, lấy trung bình tổng rubric mỗi cặp, relevant khi ≥4. Báo số người thực tế và Visual P@5 riêng với chỉ số nhãn. Các mục lịch sử dưới đây mô tả trạng thái trước cấu hình mở rộng.

## 1. Hai việc khác nhau

Hiện chạy native512-v1 trên snapshot frontal512-20261010; xem phân bố tại dataset.md. 50 tests kỹ thuật đạt, gồm pipeline 128/512, HOG 34596, LBP phủ toàn ảnh, migration 003, kiểm tra config/preprocess giữa hai SQLite, nhập/duyệt/sửa mask, top-5, start/busy/cancel và query tự tách nền. Kiểm tra dữ liệu tính lại đủ 1800 vector native512: sai lệch lớn nhất 0, 500 ứng viên hợp lệ, integrity/FK đạt. Browser thật ở chế độ headless kiểm tra ba nút xử lý, preview 512, chọn profile và bố cục desktop/mobile: không lỗi JavaScript/không tràn ngang. Model chạy thật 5 mask, nhập 15 vector; chạy lại từ web không tạo trùng. Query thường ngoài gallery tự tách nền và trả 5 ID duy nhất trong gallery thử 5 ảnh.

**Chưa có đánh giá chất lượng truy hồi đầy đủ cho 512 hoặc sau tách nền; chưa chạy đủ 600 mask.** Các số sau là thí nghiệm lịch sử **baseline 128**, không áp dụng cho config mới: validation 50 query/9 cấu hình chọn HOG-only với P@5 theo nhóm nhãn 0,684; test 50 query/5 cấu hình, selected=0,740. CSV cũ đã chuyển sang `../BTL_luu_tru_20261010/obsolete-after-native512/data/evaluation/` và có trong ZIP phục hồi. App giữ trọng số mặc định 0,1/0,45/0,45. Tên cột mean_same_species_p5 đo trùng nhóm nhãn (fox gồm nhiều loại cáo), không chứng minh taxonomy. Chưa chấm Visual P@5.

Kiểm thử kỹ thuật trả lời 'hệ thống có làm đúng đặc tả không?'. Đánh giá truy hồi trả lời 'các ảnh trả về có phù hợp về thị giác không?'. Test code pass không chứng minh chất lượng truy hồi cao. Điểm similarity cao cũng không tự chứng minh kết quả đúng.

## 2. Test kỹ thuật tối thiểu

| ID | Tình huống | Kết quả mong đợi |
| --- | --- | --- |
| UT01 | RGB/grayscale/alpha hợp lệ | RGB uint8 128×128 hoặc 512×512 theo version |
| UT02 | File hỏng, bytes rỗng | INVALID_IMAGE |
| UT03 | Crop ngoài biên | INVALID_CROP |
| UT04 | HSV ảnh một màu | 128 phần tử, sum≈1, bin màu đúng |
| UT05 | HOG ảnh có cạnh | 1764 ở 128 hoặc 34596 ở 512, finite, norm≈1 |
| UT06 | HOG ảnh đồng nhất | Zero theo cấu hình, không NaN; score policy=0 |
| UT07 | LBP | 160 phần tử, sum≈1, mỗi vùng sum≈1/16 |
| UT08 | Vector khác config ID hoặc preprocess dù cùng shape | CONFIG_MISMATCH |
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
