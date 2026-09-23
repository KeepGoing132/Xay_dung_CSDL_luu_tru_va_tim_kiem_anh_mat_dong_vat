# Hợp đồng giao tiếp nội bộ

## 1. Nguyên tắc

Đây là đặc tả hàm Python dự kiến, chưa phải API đã tồn tại. Có thể dùng dataclass hoặc typed dict, nhưng tên trường và ý nghĩa phải thống nhất trước khi chia việc. Bundle chứa đúng ba config khác nhau về feature_type; không tự chọn theo thời gian mới nhất.

## 2. Kiểu dữ liệu

| Kiểu | Trường bắt buộc | Quy tắc |
| --- | --- | --- |
| CropBox | x:int, y:int, size:int | size>0; trong ảnh sau EXIF |
| ProcessedImage | rgb, crop, preprocess_version, pixel_sha256 | rgb shape (128,128,3), dtype uint8 |
| FeatureConfig | config_id, feature_type, dimension, parameters, preprocess_version | Bất biến sau dùng |
| BundleConfig | bundle_name, hsv_config, hog_config, lbp_config | Cùng preprocess_version |
| FeatureBundle | hsv, hog, lbp, config_ids, warnings | Shape (128,), (1764,), (160,) |
| Weights | hsv:float, hog:float, lbp:float | Hữu hạn, không âm, tổng dương |
| Scores | hsv, hog, lbp, total | Float hữu hạn [0,1] |
| Candidate | image_id, processed_path, features | Một ID duy nhất |
| LoadCandidatesResult | candidates:list[Candidate], rejected:list | rejected có image_id và reason |
| SearchRequest | image_bytes, crop hoặc null, weights, bundle_name | Không yêu cầu nhãn loài |
| SearchItem | rank, image_id, processed_path, scores | rank 1..5 |
| SearchResponse | query_id, items, effective_weights, candidate_count, timings, warnings | items có đúng 5 khi thành công |
| ImportSummary | total, created, skipped, failed, errors | total=created+skipped+failed |

Vector có thể lưu NumPy trong RAM nhưng trước trả JSON hoặc ghi DB phải chuyển list số thực chuẩn, không NaN/Infinity. Tên key config_ids là hsv/hog/lbp; không suy ra ID từ vị trí ngẫu nhiên trong DB.

## 3. Hàm tiền xử lý

```python
preprocess_image(image_bytes: bytes, crop: CropBox | None) -> ProcessedImage
```

Không có SQL, không truy cập nhãn loài. Chuyển ảnh đúng pipeline dataset.md. Crop ngoài biên trả INVALID_CROP. Ảnh grayscale/alpha xử lý theo quy tắc đã thống nhất. Hash tính từ pixel RGB đã chuẩn hóa, không từ bytes PNG để tránh khác metadata.

## 4. Hàm trích xuất

```python
extract_features(image: ProcessedImage, config: BundleConfig) -> FeatureBundle
```

Preconditions: hình đúng kích thước, preprocess_version khớp config. Postconditions: đúng số chiều, finite, không âm; HSV/LBP tổng 1 trong 1e-6; HOG norm 1 hoặc zero với warning. Không tự sửa ảnh sai đầu vào bằng resize ẩn tại đây.

## 5. Hàm so sánh và xếp hạng

```python
normalize_weights(weights: Weights) -> Weights
compare_features(query: FeatureBundle, candidate: FeatureBundle,
                 weights: Weights) -> Scores
rank_candidates(query: FeatureBundle, candidates: list[Candidate],
                weights: Weights, k: int = 5) -> list[SearchItem]
```

compare kiểm tra config IDs khớp, không chỉ shape. rank dùng điểm chưa làm tròn, khóa (-total, image_id); không tự nhân bản ứng viên. Hàm generic có thể nhận k khác để test nhưng UI nghiệm thu cố định k=5. Service xác nhận có ít nhất 5 ứng viên.

## 6. Repository

```python
create_schema() -> None
upsert_species(name: str) -> int
insert_image(metadata) -> int
register_feature_config(config) -> int
save_feature(image_id: int, config_id: int, vector, warning=None) -> None
load_candidates(bundle: BundleConfig) -> LoadCandidatesResult
save_search(query_metadata, items: list[SearchItem]) -> int
get_search(query_id: int) -> SearchResponse
```

save_feature kiểm tra dimension và type từ config trong DB; mặc định không ghi đè cặp đã có. register_feature_config cùng tên nhưng tham số khác phải báo CONFIG_CONFLICT. save_search kiểm tra 5 rank liên tục, 5 ID khác nhau, score range và weighted sum trước commit.

load_candidates chỉ gallery active approved, đủ config và đúng preprocess. Nếu bỏ qua vector lỗi hoặc file ảnh thiếu, ghi image_id và reason trong rejected; service đưa số lượng và nguyên nhân vào warnings. Không im lặng bỏ ảnh lỗi.

## 7. Search service

```python
search(request: SearchRequest) -> SearchResponse
```

Thời gian trong timings: preprocess_ms, extract_ms, load_ms, rank_ms, persist_ms. duration_ms của DB = bốn giai đoạn đầu; persist_ms chỉ trả runtime hoặc log vì không thể biết chính xác tổng persist trước khi transaction hoàn thành. UI ghi rõ 'thời gian xử lý' theo định nghĩa này.

Nếu lưu lịch sử thất bại, baseline báo PERSISTENCE_ERROR thay vì hiển thị query_id giả. Có thể thiết kế chế độ tìm không lưu sau này nhưng phải đổi hợp đồng rõ ràng.

## 8. Mã lỗi

| Mã | Khi nào | Hướng xử lý |
| --- | --- | --- |
| INVALID_IMAGE | Không giải mã được/rỗng | Chọn ảnh khác |
| INVALID_CROP | Vùng cắt sai | Chọn lại vùng mặt |
| INVALID_WEIGHTS | Âm, NaN, tổng bằng 0 | Nhập trọng số hợp lệ |
| CONFIG_MISMATCH | Khác config hoặc preprocess | Dùng đúng bundle hoặc trích xuất lại |
| CONFIG_CONFLICT | Cùng tên config nhưng khác tham số | Tạo tên/version mới |
| INVALID_VECTOR | Sai chiều, NaN/Inf, chuẩn sai | Rà soát extractor và dữ liệu |
| INSUFFICIENT_GALLERY | Dưới 5 ứng viên hợp lệ | Nhập/trích xuất thêm ảnh |
| MISSING_IMAGE_FILE | Metadata có nhưng mất ảnh | Khôi phục file/đánh dấu inactive |
| PERSISTENCE_ERROR | Lỗi DB/giao dịch | Kiểm tra log, giữ nguyên dữ liệu cũ |

## 9. Quy tắc đổi hợp đồng

Chỉnh contracts trước hoặc cùng commit với code. Liệt kê caller chịu ảnh hưởng, cập nhật test tương ứng. Không tự đổi field hsv_score thành color_score ở một module rồi để module khác dùng tên cũ.
