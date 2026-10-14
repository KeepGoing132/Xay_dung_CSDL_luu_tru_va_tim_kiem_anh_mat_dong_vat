# Hợp đồng giao tiếp nội bộ

## Mở rộng refined512-v1

- Sáu config giữ tên nhóm, thay dimension/parameters theo features. Repository gọi `calibrated_specs` trước đăng ký; calibration thiếu/sai trả CONFIG_MISMATCH, calibration khác cấu hình đã lưu trả CONFIG_CONFLICT. Không fallback sang thang điểm mặc định.
- `BundleConfig.signature` là SHA-256 canonical JSON của tên/type/dimension/parameters/preprocess từng nhóm. `FeatureBundle.config_signature` phải khớp khi so sánh; cùng ID số nhưng khác tham số vẫn bị từ chối. `similarities` của refined chứa cả sáu nhóm, các bundle cũ giữ mapping extras như trước. Giá trị calibration là bất biến; score function không đọc file/DB.
- HTTP `query.spatial_prior` là PNG data URL hoặc null; `query.preview_notes` có chú thích HOG/LBP. Cả hai additive, không thay field cũ. Preview sử dụng bundle parameters; LBP đa mức chỉ minh họa mức đầu và ghi chú rõ. Selector/API hỗ trợ thêm refined512-v1.
- History lưu `config_signature`, thuật toán `calibrated-cbir-v1` cùng đủ parameters/dimensions/calibration hash. Không đổi schema. Caller cập nhật: extractor/repository/similarity, HTTP adapter/frontend, script chuẩn bị/đối chiếu/verify, tests.
- `Repository.backup_to(destination)` dùng SQLite backup API, không ghi đè file có sẵn và kiểm tra integrity. CLI chuẩn bị giữ bản demo trước khi nhập dữ liệu mới.

## 1. Nguyên tắc

Các kiểu dữ liệu đã triển khai bằng dataclass trong `backend/src/models.py`; chữ ký bên dưới mô tả hợp đồng nghiệp vụ, tên phương thức cụ thể đối chiếu mã nguồn. Bundle có ba config ở các profile cũ, sáu config ở expanded512-v1/refined512-v1; không tự chọn theo thời gian mới nhất.

### Mở rộng ngày 13/10/2026

- `BundleConfig.configs` và `FeatureBundle.vectors` trả mapping tất cả các nhóm. Thuộc tính hsv/hog/lbp được giữ tương thích; nhóm bổ sung nằm trong `extras`. `config_ids` phải khớp toàn bộ mapping; `FeatureBundle.similarities` chứa metric/scale cho nhóm mới và cũng phải khớp khi so sánh.
- `Weights.from_dict`, `Weights.as_dict`, `Scores.as_dict`, `Scores.contributions` dùng khóa hsv/hog/lbp/spatial_hsv/color_moments/glcm theo profile. Trọng số nhóm không tồn tại bị từ chối; nhóm bổ sung không có trọng số có hiệu lực 0 để chạy ablation. Điểm tổng bằng tổng tất cả đóng góp.
- HTTP search nhận trọng số từng nhóm bằng tên tương ứng; khi bỏ qua dùng mặc định của profile. `items[].scores`, `contributions`, `query.dimensions` là mapping động; `query.extra_vectors` trả các vector mới để minh họa; `feature_labels` phục vụ nhãn hiển thị. History trả cùng mapping `scores` và giữ các cột điểm cũ tương thích. UI tải cấu hình nhóm từ server, không tự tính đặc trưng.
- `load_candidates` kiểm tra giải mã, mode/kích thước/checksum pixel của file processed, đủ vector và chuẩn hóa. Dashboard `valid_candidates`, `gallery_ready` (≥5), `acceptance_ready` (≥500) cùng dùng tập ứng viên hợp lệ của service; `approved_gallery` vẫn là số metadata đã duyệt. `rejected_candidates` có image_id/processed_path/reason. Search thiếu 5 ứng viên trả cùng chi tiết trong error; khi đủ thì đưa lý do loại vào warnings.
- `DatasetProcessingService.run(..., limit=N)` giới hạn cả tách nền và trích xuất trên N đường dẫn nguồn được sắp xếp như model. Nhập thử giữ các dòng manifest của nhóm ngoài phạm vi; quyết định duyệt cũ không bị đặt lại.
- `timings` giữ các trường cũ, thêm segmentation_ms, preview_ms và request_ms ở HTTP. request_ms là thời gian phía máy chủ từ bắt đầu endpoint tới trước encode JSON; không bao gồm mạng/render trình duyệt. Công việc tạo preview chạy trong threadpool. Lịch sử lưu thời gian truy hồi theo định nghĩa cũ.
- Bên gọi được cập nhật: Repository/IngestionService/SearchService, HTTP adapter, frontend, import/evaluate/export_statistics/demo_search/verify scripts và tests. Không đổi công thức hoặc dimension của các config cũ.

## 2. Kiểu dữ liệu

| Kiểu | Trường bắt buộc | Quy tắc |
| --- | --- | --- |
| CropBox | x:int, y:int, size:int | size>0; trong ảnh sau EXIF |
| ProcessedImage | rgb, crop, preprocess_version, pixel_sha256 | rgb shape (size,size,3), uint8; size=128 hoặc 512 theo version |
| FeatureConfig | config_id, feature_type, dimension, parameters, preprocess_version | Bất biến sau dùng |
| BundleConfig | bundle_name, hsv_config, hog_config, lbp_config | Cùng preprocess_version |
| FeatureBundle | hsv, hog, lbp, config_ids, warnings, preprocess_version | Số chiều theo config của từng profile; xem features, không suy từ kích thước ảnh |
| Weights | hsv:float, hog:float, lbp:float | Hữu hạn, không âm, tổng dương |
| Scores | hsv, hog, lbp, total | Float hữu hạn [0,1] |
| Candidate | image_id, processed_path, features | Một ID duy nhất |
| LoadCandidatesResult | candidates:list[Candidate], rejected:list | rejected có image_id và reason |
| SearchRequest | image_bytes, crop hoặc null, weights, bundle_name | Không yêu cầu nhãn loài |
| SearchItem | rank, image_id, processed_path, scores | rank 1..5 |
| SearchResponse | query_id, items, effective_weights, candidate_count, timings, warnings | items có đúng 5 khi thành công |
| ImportSummary | total, created, skipped, failed, errors | total=created+skipped+failed |

Vector có thể lưu NumPy trong RAM nhưng trước trả JSON hoặc ghi DB phải chuyển list số thực chuẩn, không NaN/Infinity. Tên key config_ids là hsv/hog/lbp và các nhóm extras của profile; không suy ra ID từ vị trí ngẫu nhiên trong DB.

## 3. Hàm tiền xử lý

```python
preprocess_image(image_bytes: bytes, crop: CropBox | None) -> ProcessedImage
```

Không có SQL, không truy cập nhãn loài. Chuyển ảnh đúng pipeline dataset.md. Crop ngoài biên trả INVALID_CROP. Ảnh grayscale/alpha xử lý theo quy tắc đã thống nhất. Hash tính từ pixel RGB đã chuẩn hóa, không từ bytes PNG để tránh khác metadata.

Tham số keyword `preprocess_version` mặc định `preprocess-v1`; AppConfig mặc định chọn `refined512-v1` với `preprocess-512-v1` (cần calibration đã chuẩn bị). Profile nền trắng 512 truyền `preprocess-bg-white-512-v1` ở ingestion/search/evaluate; profile nền trắng 128 cũ vẫn được hỗ trợ. Profile nền trắng yêu cầu alpha có nền trong suốt và foreground không rỗng, nếu sai trả `BACKGROUND_REQUIRED`. Không chạy segmentation trong hàm tiền xử lý. SearchRequest.bundle_name phải khớp AppConfig.bundle_name; HTTP adapter tự truyền bundle đang chọn.

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

compare kiểm tra config IDs, preprocess_version và shape khớp. Điều này bảo vệ trường hợp hai SQLite độc lập có config ID số giống nhau. rank dùng điểm chưa làm tròn, khóa (-total, image_id); không tự nhân bản ứng viên. Hàm generic có thể nhận k khác để test nhưng UI nghiệm thu cố định k=5. Service xác nhận có ít nhất 5 ứng viên.

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
original_paths(image_ids: list[int]) -> dict[int, str]
audit_image_records() -> list[dict]
audit_feature_records() -> list[dict]
set_image_qualities(decisions) -> None
update_image_attributions(updates) -> None
retire_other_mask_versions(current) -> None
```

save_feature kiểm tra dimension và type từ config trong DB; mặc định không ghi đè cặp đã có. register_feature_config cùng tên nhưng tham số khác phải báo CONFIG_CONFLICT. save_search kiểm tra 5 rank liên tục, 5 ID khác nhau, score range và weighted sum trước commit.

original_paths lấy đường dẫn nguồn theo lô, tham số hóa ID; ID không tồn tại được bỏ khỏi mapping. Hai phương thức audit trả metadata/vector cho công cụ đối soát, không thay đổi dữ liệu. SQL nằm trong Repository.

HTTP adapter bổ sung field image là data URL ảnh RGB để hiển thị, không đổi SearchItem hoặc công thức tính điểm. Native ưu tiên original_path, thiếu file nguồn thì dùng processed_path; profile nền trắng dùng processed nền trắng. Search/history dùng cùng quy tắc, kiểm tra đường dẫn nằm trong data. Query preview và vector đều từ ảnh đã xử lý theo kích thước của profile.

`set_image_qualities` cập nhật lô trong một transaction. `update_image_attributions` gắn đường dẫn mask bất biến và ghi công theo checksum. `retire_other_mask_versions` đánh dấu inactive/rejected bản mask cũ cùng group_id/preprocess khi bản sửa mới đã nhập thành công; ảnh/vector cũ vẫn giữ để đọc lịch sử.

load_candidates chỉ gallery active approved, đủ config và đúng preprocess. Nếu bỏ qua vector lỗi hoặc file ảnh thiếu, ghi image_id và reason trong rejected; service đưa số lượng và nguyên nhân vào warnings. Không im lặng bỏ ảnh lỗi.

Cache gallery (30/09/2026): `gallery_fingerprint` gồm revision CSDL, config IDs, preprocess_version và dấu tệp của toàn bộ gallery có metadata hợp lệ, kể cả tệp đang thiếu. Chỉnh vector tại chỗ hoặc khôi phục tệp làm cache hết hiệu lực. Fingerprint và payload được giữ trong cùng tuple. Đường dẫn vượt data bị ghi `INVALID_IMAGE_PATH` trong rejected.

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

### HTTP profile và xử lý dataset

`GET /`, `/api/dashboard`, `/api/history/{id}` và `POST /api/search` nhận query parameter `profile`. Chỉ nhận các profile trong AppConfig; giao diện cung cấp native512, background512, expanded512 và refined512. Profile không có trong danh sách báo lỗi. Với background512, PNG alpha hợp lệ đi thẳng vào pipeline; ảnh thường được DatasetProcessingService crop/chuẩn hóa 512 rồi chạy model cục bộ, sau đó cùng pipeline nền trắng. Crop được áp dụng một lần. Thời gian segmentation chưa nằm trong timings của SearchService.

| API | Hợp đồng |
| --- | --- |
| GET /api/processing | offset≥0, limit=1..48, ready_only; trả catalog, counts, latest job |
| POST /api/processing | JSON action=remove_background/extract_features/pipeline; limit=null hoặc số ảnh chạy thử |
| POST /api/processing/cancel | Yêu cầu dừng tác vụ đang chạy; giữ kết quả đã lưu thành công |
| POST /api/processing/review | JSON source_ids là index trong manifest và quality_status=approved/rejected/pending; chỉ duyệt mask đã trích xuất và checksum khớp |
| GET /api/processing/preview/{source_id}/{kind} | kind=original/mask; chỉ trả ảnh trong manifest, không nhận đường dẫn tùy ý |

Một worker dataset tại một thời điểm; start khi busy trả 409. Job lưu trạng thái running/completed/failed/cancelled/interrupted, phase, completed/total, lỗi và kết quả; refresh trang không tạo lại job. Tác vụ đầy đủ yêu cầu đủ cutout, tác vụ thử cho phép thiếu. Model chạy subprocess từ môi trường riêng; trọng số giữ nguyên. Nhập mặc định pending, người dùng duyệt mask để tham gia gallery. File mask đầu vào tính đặc trưng được chụp bản bất biến; sửa mask chuẩn rồi chạy lại sẽ tạo phiên bản mới. UI gọi service, SQL vẫn nằm trong Repository.

Chỉnh contracts trước hoặc cùng commit với code. Liệt kê caller chịu ảnh hưởng, cập nhật test tương ứng. Không tự đổi field hsv_score thành color_score ở một module rồi để module khác dùng tên cũ.
