# Bộ dữ liệu và tiền xử lý

## Snapshot đang dùng: frontal512-20261010

Nguồn duy nhất là AFHQ v2 của NAVER. Chọn 600 PNG màu RGB 512×512 từ nguồn đã tải, giữ nguyên byte file phát hành; không phóng ảnh nhỏ lên. Đề yêu cầu ít nhất 500 ảnh mặt động vật khác nhau, không bắt buộc 20 loài. Bộ mới ưu tiên mặt chính diện và độ rõ.

| Nhóm nhãn | Gallery | Validation | Test | Tổng |
| --- | ---: | ---: | ---: | ---: |
| cat | 130 | 13 | 12 | 155 |
| dog | 195 | 20 | 20 | 235 |
| tiger | 60 | 5 | 5 | 70 |
| lion | 65 | 5 | 5 | 75 |
| fox | 23 | 2 | 3 | 28 |
| cheetah | 27 | 5 | 5 | 37 |
| Tổng | 500 | 50 | 50 | 600 |

Đây là sáu nhóm nhãn, không phải sáu loài đã kiểm chứng taxonomy: fox gồm nhiều loại cáo; cat/dog có nhiều giống. Tập không cân bằng. Nhãn phục vụ thống kê/đánh giá, không lọc ứng viên truy hồi.

- SQLite mặc định: `data/native512.db`.
- Manifest: `data/manifests/frontal512_manifest.csv`.
- Nguồn từng ảnh: `data/manifests/frontal512_sources.csv`; giấy phép tại [sources.md](sources.md).
- Ảnh nguồn: `data/original/{gallery,validation,test}/{nhóm}/`, đều RGB 512×512.
- Ảnh tính đặc trưng native: dùng trực tiếp ảnh nguồn RGB 512×512, original_path và processed_path cùng file khi pixel đã đúng; không tạo thêm bản 128.
- Mask chỉnh tay: `data/background_removed/all-images/`; snapshot mask nhập DB: `data/background_removed/versions/`.
- RGB nền trắng tính đặc trưng: `data/processed/background512-white-v1/`, đều 512×512; SQLite riêng `data/background512_white.db`.
- Bảng duyệt cuối: `data/review/frontal512-20261010/selected-*.jpg` (24 bảng).

## Duyệt chất lượng

Đã xem 1.560 ứng viên trên 44 bảng: 10 cat, 14 dog và 20 wild. Chọn mắt gần ngang, mũi gần trục giữa, mặt lớn ở giữa, nhìn được cả hai mắt–mũi–miệng, lông/cạnh rõ và có màu. Sau đó xem lại bộ chọn ban đầu trên 24 bảng lớn hơn, loại thêm và bổ sung từ ứng viên đã duyệt. Quyết định: `data/review/frontal512-20261010/decisions.json`; mã duyệt nối với nguồn CSV.

Loại ảnh quay/nghiêng/ngửa rõ, nhắm mắt, che mặt, tối hoặc mờ, mặt quá nhỏ, nhãn wild khó xác định. Không dùng ảnh AI. Duyệt bằng quan sát, chưa đo góc đầu/tỷ lệ mặt bằng landmark; không tuyên bố mọi ảnh đạt góc chính diện tuyệt đối. Nguồn đã căn chỉnh mặt nhưng tỷ lệ tai/mõm vẫn khác giữa nhóm.

## Tách tập và chống trùng

Validation/test nằm ngoài gallery. Toàn bộ 600 ảnh có 0 trùng SHA-256 file, 0 trùng pixel RGB, 0 cặp dHash 256 bit có Hamming ≤5 và 0 group_id xuyên split. Bằng chứng: `data/statistics/native512-v1/frontal512-verification.json`.

AFHQ không cung cấp ID cá thể từng ảnh. group_id truy vết file nguồn, không chứng minh 600 cá thể riêng; dHash không phát hiện mọi trường hợp cùng cá thể/cảnh. Không dùng lại snapshot AFHQ cũ làm query bộ mới.

Manifest giữ relative_path, species_name, source_url, license_note, split, group_id, crop_x/y/size, quality_status, review_note, source_archive và source_member. Đường dẫn tính từ data/.

## Pipeline preprocess-512-v1

1. Giải mã/sửa EXIF và chuyển hoặc ghép thành RGB.
2. Crop vuông theo manifest; nếu trống thì center crop. Nguồn mới vuông 512×512 nên giữ toàn ảnh.
3. Giữ RGB 512×512; nguồn đã vuông/đúng kích thước không nội suy lại. Query có kích thước khác được crop và resize 512 bằng cùng pipeline.
4. Trích HSV 128, HOG 34596, LBP 160 theo native512-v1; lưu checksum nguồn và pixel xử lý.
5. Chỉ gallery active + approved có đủ vector cùng config/preprocess tham gia tìm kiếm.

Gallery và query dùng chung pipeline. Các config 512 mới được tạo riêng, không ghi đè baseline-v1 128. Kết quả/lịch sử native và ảnh query hiển thị 512×512.

Profile tách nền có cấu hình/SQLite riêng: [background-import.md](background-import.md). Model giữ nguyên. Đã chạy thật 5 mask RGBA 512 và nhập/duyệt 15 vector; chưa tách nền toàn bộ 600 ảnh mới. Mask mới mặc định pending, cần duyệt trước truy hồi.

## Kiểm tra và dữ liệu cũ

SQLite có 600 ảnh/1800 vector, integrity=ok, không lỗi khóa ngoại; 500 ứng viên hợp lệ. Tái tính đủ 1800 vector khớp tuyệt đối. Script: `scripts/verify_frontal_dataset.py`. Visual P@5 do người chấm chưa thực hiện; chỉ số theo nhãn không phải độ chính xác mô hình.

Snapshot mixed-20 và runtime 128 đã rời runtime. ZIP giữ trong project để phục hồi trạng thái 600 ảnh ngay trước chuyển 512: `data/backups/before-native512-20261010.zip`, checksum trong JSON cùng tên. ZIP mixed-20 cũ và bản sao dư đã chuyển vào `../BTL_luu_tru_20261010/obsolete-after-native512/`; ảnh cũ ở obsolete-after-frontal512, archive tải chưa dùng ở unused/data. Xóa bị kiểm duyệt tự động chặn, chưa giải phóng dung lượng. `scripts/cleanup_obsolete_data.ps1` mặc định chỉ xem; người dùng chạy -Purge để xóa.
