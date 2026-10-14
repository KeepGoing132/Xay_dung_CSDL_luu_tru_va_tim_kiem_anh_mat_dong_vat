## Đưa mã nguồn lên GitHub — 2026-10-14

- Theo yêu cầu người dùng, đưa bản dự án hiện tại lên repository `KeepGoing132/Xay_dung_CSDL_luu_tru_va_tim_kiem_anh_mat_dong_vat`, loại toàn bộ thư mục `data/` bằng quy tắc `/data/` trong `.gitignore`. README ghi rõ cần bổ sung dữ liệu riêng để chạy demo. Giữ các quy tắc bỏ qua môi trường, tệp tạm và trọng số ONNX đã có.
- Đã kiểm tra danh sách staged: không có file trong `data/`, không có file vượt 100 MiB; quét mẫu token/private key không phát hiện file phù hợp. `git diff --cached --check` ghi nhận khoảng trắng cuối dòng/cuối file đã có trong nguồn và giấy phép font; không sửa mã hoặc giấy phép chỉ để làm sạch kiểm tra.
- Đã commit bản hiện tại (`6ccc7b6`), tích hợp lịch sử tài liệu của repository đích (`1fed830`), giữ bản hiện hành ở các đường dẫn trùng nhau và giữ ba tài liệu chỉ có trên remote. Push nhánh `main` thành công; `git ls-remote` xác nhận remote khớp commit local. Kiểm tra toàn bộ lịch sử đưa lên không có đường dẫn `data/`; working tree sạch sau push. Remote cũ được giữ dưới tên `previous-origin`.
- Chưa chạy lại kiểm thử ứng dụng, đánh giá ảnh hoặc model trong nhiệm vụ chỉ đưa mã nguồn lên Git. Các tài liệu kế hoạch/demo cũ được giữ từ remote có thể mô tả thiết kế trước đây; README và nhật ký hiện hành là điểm đọc trạng thái thực tế. Bước tiếp theo khi chạy trên máy khác: bổ sung riêng `data/`, tạo môi trường và làm theo README.

## Cải tiến vùng tính đặc trưng và hiệu chỉnh điểm — 2026-10-13

- Đã triển khai và chạy thật profile riêng refined512-v1; mặc định runtime mới và lệnh README dùng profile này. Cùng RGB 512×512/preprocess-512-v1, sáu nhóm tổng 11444 chiều. Ưu tiên trung tâm bằng trọng số theo vị trí, HOG hai mức cell, LBP ba bán kính, GLCM bỏ ASM. Công thức/giới hạn nằm tại features. Vùng ưu tiên là giả định mặt nằm giữa, không phải mask phát hiện mặt; không chạy thêm model hoặc tự duyệt mask cũ.
- Hiệu chỉnh thang từng chiều Moments/GLCM và thang điểm cả sáu nhóm từ 500 gallery approved/4096 cặp khác nhau, không dùng nhãn hoặc validation/test. Calibration đóng băng tại data/calibration/refined512-v1/gallery.json. Sáu median score đo được xấp xỉ .5; không diễn giải là xác suất liên quan. Trọng số khởi đầu cân bằng ba khía cạnh màu/hình/kết cấu, chưa gọi là tối ưu; không thay theo kết quả test.
- Nhập thành công 600 ảnh/3600 vector vào data/refined512.db: created=600, skipped=0, failed=0. Kích thước sau nhập 144957440 byte. Ảnh nguồn được dùng lại, không ghi đè ảnh hoặc vector cũ. Bản sao demo trước thay ở data/backups/before-refined512-20261013; CLI chuẩn bị cũng giữ bản sao tại data/backups/before-refined512. Snapshot source trước sửa tại tmp/before-refined512-20261013. Đối chiếu hash nội dung năm bảng ở expanded/native/background với backup đều khớp; bằng chứng legacy-preservation.json.
- Thêm dấu cấu hình đầy đủ vào FeatureBundle, so sánh cả tham số khi hai CSDL có ID số trùng nhau. History lưu dấu cấu hình/calibration và thuật toán mới trong JSON, không đổi schema. Runtime thiếu/sai calibration hoặc bị thay tham số sẽ báo lỗi; không fallback ngầm. API preview gọi đúng cấu hình, minh họa HOG hai mức và ghi rõ LBP chỉ hiển thị R=1. UI có profile mới, bản đồ trọng số và slider giữ được trọng số phân số.
- Kiểm tra cuối: 72 pytest tests đạt, một cảnh báo deprecation Starlette/httpx như trước; Node syntax và frontend_render.test.cjs đạt. Test mới gồm ảnh hưởng vị trí màu, GLCM đối chiếu đếm cặp bằng tay, ảnh hằng/zero-vector, nhiều mức, calibration xác định/không dùng nhãn hoặc query, file calibration bị đổi, config signature, vector khác chiều dù HOG zero, round-trip HTTP/history. Python AST và diff so snapshot đạt; không đổi dependency hoặc stage/commit.
- verify_frontal_dataset refined tính lại đủ 3600 vector, sai lệch lớn nhất **0.0**. 600 nguồn/metadata/pixel đúng; 500 gallery/50 validation/50 test; 500 candidates, 0 rejected; không trùng byte/pixel, không gần trùng dHash256 Hamming≤5, không group xuyên split; integrity/FK đạt. Thống kê min/max/mean/std từng chiều và summary sáu nhóm tại data/statistics/refined512-v1.
- verify_web_runtime đạt trên bản sao cả expanded/refined, dùng đúng default weights của từng profile: HTTP assets/dashboard, top-5, history, lỗi thiếu ảnh=422/history thiếu=404, chạy ngoài cwd. Refined trả 5 ID [39,76,102,80,20] cho query smoke; không coi đây là chỉ số chất lượng. Script không ghi truy vấn vào CSDL thật; refined thực có 0 search ở thời điểm bàn giao. Đã khởi động lại server do trợ lý mở ở http://127.0.0.1:8005 với refined, HTTP kiểm tra 600 ảnh/500 ứng viên, acceptance_ready=true, tổng 11444 chiều và selector đúng.
- Đối chiếu default expanded/refined trên cùng 50 validation và 50 test, không dùng nhãn: mỗi split 500 dòng kết quả, từng query/profile có đúng 5 nguồn ảnh khác nhau, không lỗi. HTML/CSV/metadata tại artifacts/evaluation/refined512-v1; 423 cặp validation và 412 cặp test cần chấm. Đã kiểm tra cấu trúc HTML/CSV và xem ảnh ghép của query validation 1/21/41 để xác nhận hiển thị. Bảng judgments vẫn trống, visual_p5=null; không bịa điểm chấm người hoặc nhận là cải thiện thị giác đã được chứng minh.
- Giới hạn/bước tiếp: công cụ trình duyệt trả apps/browsers rỗng nên chưa thao tác trực quan desktop/mobile trong trình duyệt; chỉ kiểm tra HTTP, DOM stub và ảnh minh họa. Chưa có Visual P@5; dùng báo cáo đối chiếu để chấm thật, chọn cấu hình trên validation và giữ test độc lập. Không tự thay trọng số bằng nhãn loài. Background512 vẫn bộ demo chưa đủ gallery như trước.

## Mở rộng sáu nhóm đặc trưng và sửa luồng truy hồi — 2026-10-13

- Theo yêu cầu bổ sung đặc trưng và phần còn thiếu, thêm profile expanded512-v1 (SQLite/config riêng), tổng 35480 chiều. Ba nhóm bổ sung là Spatial HSV 512, Color Moments 36, GLCM 48; giữ công thức/cấu hình baseline/native/background cũ. Công thức chỉ định nghĩa tại features; giao tiếp tại contracts, schema tại database. Không huấn luyện model hoặc lọc ứng viên theo nhãn.
- Đã nhập đủ 600 ảnh/3600 vector vào data/expanded512.db, created=600/skipped=0/failed=0; gallery/validation/test=500/50/50. Dùng lại ảnh nguồn RGB đúng chuẩn, không tạo bản sao processed dư. CSDL mới có kích thước 450.330.624 byte ở thời điểm kiểm tra.
- Backup hai SQLite cũ tại data/backups/before-expanded512-20261013, integrity đạt trước nhập. Migration 004 được kiểm chứng trên bản sao native512: năm bảng dữ liệu cũ giữ nguyên hash nội dung, FK/integrity đạt, chạy lại idempotent. Kiểm tra cuối xác nhận nội dung cả native512.db và background512_white.db thật vẫn khớp bản backup; không thay ảnh/vector/trạng thái duyệt cũ. Snapshot code trước sửa tại tmp/before-expanded512-20261013; không stage/commit các file của workspace.
- Sửa ba lỗi đã tái hiện: gallery kiểm tra giải mã/mode/kích thước/checksum pixel và vector; ảnh thiếu/hỏng/đổi pixel bị loại có image_id/đường dẫn/lý do, không còn ghi query thành công trong ca gallery không đủ. Dashboard readiness dựa trên cùng tập ứng viên hợp lệ. Limit chạy thử áp dụng cho cả trích xuất, giữ manifest và quyết định duyệt ngoài phạm vi; test limit=1 với 6 mask chỉ nhập 1.
- Giao diện có bộ chọn sáu đặc trưng, sáu thanh trọng số, preset từng nhóm/bằng nhau/validation, bảng điểm và biểu đồ đóng góp động, biểu đồ ba vector bổ sung, xuất kết quả JSON, chi tiết gallery lỗi. Preset validation chỉ xuất hiện khi signature khớp dữ liệu/config. Thời gian HTTP bổ sung segmentation/preview/request; tạo preview chuyển sang threadpool. History mới lưu đủ điểm thành phần, tham số, versions thư viện và signature gallery.
- Đánh giá thật: 50 validation/15 run và 50 test/11 run, 500 ứng viên, tất cả 0 failed. Validation chọn HOG 0.6 + Spatial HSV 0.2 + GLCM 0.2, P@5 theo nhãn=0.568; trên test=0.544, thấp hơn HOG-only=0.604. Không chỉnh trọng số theo test, không nhận là tăng chất lượng toàn diện. Bảng đầy đủ nằm trong testing-evaluation, CSV/JSON tại data/evaluation/expanded512-v1. Có mean_all_known_p5, macro theo nhãn, kiểm tra rò rỉ group/path/byte/pixel và signature trước dùng trọng số. Xuất pool để chấm người thật cùng script score_judgments.py; chưa điền điểm hoặc tạo Visual P@5 giả.
- Đã xuất min/max/mean/std(ddof=0) từng chiều, norm và zero-vector-rate cho sáu bộ tại data/statistics/expanded512-v1. verify_frontal_dataset tính lại đủ 3600 vector, sai lệch tuyệt đối lớn nhất 2.0816681711721685e-17; 500 candidates/0 rejected, nguồn/pixel/metadata khớp, không trùng byte/pixel/gần trùng dHash256 Hamming≤5 hoặc group xuyên split; integrity/FK đạt.
- Kiểm tra code: toàn bộ 64 pytest tests đạt (50 cũ + 14 mới), có cảnh báo deprecation Starlette/httpx như trước. Node --check và tests/frontend_render.test.cjs đạt: sáu cột điểm/đóng góp, vector preview, thời gian, sức khỏe gallery, escape nội dung lỗi và tiếng Việt. Kiểm tra riêng lại các test mở rộng/đánh giá sau sửa chữ giao diện. Đã rà diff so với snapshot, không có trailing whitespace mới; không thay dependency.
- verify_web_runtime đạt trên bản sao của cả native512 và expanded512: trang/assets/dashboard 200, 500 ứng viên/5 ID duy nhất, history giữ ảnh/điểm, lỗi thiếu ảnh=422/không có history=404, chạy ngoài cwd. Native trả [80,216,31,586,520]; expanded với ba trọng số gửi 0.1/0.45/0.45 và extras mặc định rồi chuẩn hóa trả [216,80,102,520,70]. Không ghi truy vấn thử vào CSDL thật. Server riêng được khởi động ở http://127.0.0.1:8005 với profile expanded512-v1; HTTP kiểm tra đủ sáu slider, preset validation và 500 ứng viên hợp lệ.
- Giới hạn: chưa kiểm tra trực quan desktop/mobile vì công cụ báo apps/browsers rỗng và IAB không khả dụng; DOM stub/HTTP không thay thế kiểm tra trình duyệt. Chưa dựng môi trường sạch, chưa có Visual P@5 hoặc chạy model toàn bộ 600 ảnh. Background512 vẫn 2 approved/3 rejected, không tự duyệt lại. Bước tiếp theo là mở URL trên để kiểm tra bố cục và chấm pool thị giác; nếu dùng tách nền thì cần xử lý/duyệt đủ gallery riêng. Bằng chứng máy đọc: data/statistics/expanded512-v1/{frontal512-verification,migration4-verification,change-audit}.json.

## Rà soát đề xuất cải tiến — 2026-10-13

- Phạm vi: đọc README, requirements/features/contracts/database/testing-evaluation và code liên quan; chỉ bổ sung nhật ký này, không sửa mã ứng dụng, cấu hình, ảnh, vector hoặc CSDL thật. Không stage/commit các thay đổi đã có trong workspace.
- Đọc hai SQLite hiện hành bằng mode=ro: native512 có 600 ảnh (500 gallery approved/active, 50 validation, 50 test), 1800 vector; tệp DB 445.591.552 byte. Background512 có 5 ảnh/15 vector nhưng chỉ **2 gallery approved/active**, 3 rejected/inactive. Con số 5 gallery được duyệt trong README và các mục ngày 10/10 là trạng thái cũ; profile tách nền hiện chưa đủ top-5 hoặc nghiệm thu 500 ảnh.
- Kiểm tra: `python -m pytest -p no:cacheprovider -q` đạt 50 tests, có cảnh báo deprecation Starlette/TestClient/httpx. `scripts/verify_web_runtime.py` đạt trên bản sao SQLite: trang/asset/dashboard 200, 500 ứng viên trả 5 ID duy nhất [80,216,31,586,520], history khớp, thiếu ảnh=422, thiếu history=404; chạy được ngoài cwd project. CSDL thật chỉ mở đọc để sao lưu.
- Tái hiện riêng bằng fixture trong thư mục tạm: (1) gallery 5 ảnh mất một file thì load_candidates còn 4 nhưng public_stats vẫn gallery_ready=true; acceptance_ready cũng đang dựa trên số metadata approved thay vì ứng viên hợp lệ. (2) Thay một PNG gallery tạm bằng bytes hỏng: load_candidates vẫn nhận đủ 5, POST /api/search trả 500 trong khi đã lưu 1 query. (3) Có 6 mask tạm, gọi DatasetProcessingService.run('extract_features', limit=1) vẫn nhập cả 6 ảnh. Đây là lỗi đã tái hiện, chưa sửa; các kiểm tra bổ sung này chưa được đưa vào bộ regression test.
- Khoảng trống đánh giá: chưa thấy kết quả validation/test 512 trong thư mục evaluation hiện hành; chỉ có báo cáo smoke tách nền. Tài liệu xác nhận chưa chấm Visual P@5. Cần chạy đánh giá trên query tách biệt, chọn trọng số bằng validation và báo riêng độ trùng nhãn với độ phù hợp thị giác. Đo hiệu năng đầy đủ cần tính thêm segmentation và tạo ảnh phản hồi; chưa đo trong lượt này.
- Quản lý phiên bản: `git ls-files` hiện chỉ có README.md; các thư mục code/tests/docs vẫn untracked. Cần tạo commit mốc có chọn lọc trước các thay đổi tiếp theo, không đưa dữ liệu/model/môi trường vào Git.
- Chưa kiểm tra: giao diện trực quan desktop/mobile hiện tại, dựng môi trường sạch, tính lại toàn bộ vector/kiểm tra pixel, model trên toàn bộ dataset hoặc chất lượng truy hồi 512. Bước tiếp theo: sửa lỗi kiểm tra gallery/ảnh hỏng và giới hạn trích xuất kèm regression tests, sau đó hoàn thiện dữ liệu tách nền và thực nghiệm đánh giá. Không tự duyệt lại các mask đã bị loại.

## Đồng bộ font và tăng cỡ chữ giao diện — 2026-10-10

- Đọc README/progress, rà soát typography trong template/app.css/motion.css của cả năm trang. Thay font tiêu đề/nhãn/nội dung bằng Be Vietnam Pro (400/500/600/700); Fira Code giữ cho điểm số, ID và mã cấu hình. Tải nguyên tệp từ kho Google Fonts, lưu năm TTF cùng hai OFL trong frontend/static/fonts; fonts/README ghi URL, SHA-256 và vai trò. Template preload Regular/SemiBold, bỏ Google Fonts bên ngoài; font-display:swap và font dự phòng vẫn có.
- Thang chữ dùng biến CSS: nhãn phụ 12–14 px, nội dung/điều khiển 15–16 px, tiêu đề panel 18 px, tiêu đề trang responsive 32–68 px. Rà soát các font-size và font shorthand cũ 8–11 px, nâng toàn bộ; tăng độ sáng chữ phụ, giãn dòng tiếng Việt và bỏ font monospace khỏi tiêu đề/nhãn đọc thông thường. Sửa cả các override font trong motion.css để không bị quay về chữ nhỏ ở mobile.
- Tăng khoảng cách bảng điểm/menu, cho thông tin thẻ ảnh và chú thích xuống dòng, giữ đủ 5 kết quả, sidebar có thể cuộn, mã cấu hình dài tự ngắt. Biểu đồ dùng số cột thực tế theo số phần tử, rộng tối thiểu 36 px để nhãn lớn hơn có chỗ; không đổi số liệu. Không thay JS xử lý, model, API, cấu hình vector, ảnh hoặc SQLite.
- Kiểm tra HTTP: trang chủ/CSS hiện hành với hash mới và năm font đều 200, nội dung font/CSS tải về khớp file; HTML no-cache và không còn URL Google Fonts. FontTools xác nhận đủ ký tự tiếng Việt của UI ở cả bốn weight; Pillow đọc đúng family/style và dấu của câu thử ở 12/14/16/18/34/68 px nằm trong line-height 1,4. Không còn khai báo chữ nhỏ hơn 12 px trong hai CSS. Node --check hai JS và git diff --check đạt; đối chiếu nội dung trước/sau chỉ đổi font, màu chữ và khoảng cách/bố cục liên quan. Không chạy lại model hoặc bộ test nghiệp vụ cho thay đổi trình bày.
- Chưa xác nhận trực quan trên desktop/mobile hoặc đo tràn bố cục bằng trình duyệt. Parser CSS tinycss2 không có trong môi trường, nên không nhận là đã kiểm tra cú pháp bằng parser. Bước tiếp theo: tải lại http://127.0.0.1:8004 để xem font mới; server hiện có phục vụ thay đổi trực tiếp.

## Thiết kế lại thông báo xử lý ảnh — 2026-10-10

- Theo ảnh người dùng gửi, thay khung pre nền hồng/chữ đỏ bằng thẻ nền tối, viền dịu, icon, tiêu đề và nhãn trạng thái trong frontend/templates/index.html và frontend/static/app.css. Dừng tác vụ dùng màu xanh/icon pause và nhãn Có thể tiếp tục; interrupted dùng màu vàng, lỗi thật dùng màu hồng đỏ. Có bố cục co giãn trên mobile và chuyển động xuất hiện nhẹ, chịu cùng cài đặt giảm chuyển động hiện có.
- app.js render thông báo theo job.status, Việt hóa thông báo interrupted đã biết và viết lại câu dừng tác vụ cho dễ đọc. Giữ nguyên các nội dung lỗi khác, newline và đường dẫn bằng textContent; không chèn error vào HTML, không đổi backend/job, model, tiến độ hoặc dữ liệu đã lưu.
- Node --check đạt. Kiểm tra hàm render thực tế trong Node VM với các nút DOM giả: cancelled, failed, interrupted và không có thông báo đều đạt; nội dung lỗi chứa markup được giữ nguyên dưới dạng text. Trang chủ hiện hành tại 127.0.0.1:8004 HTTP 200, có DOM thông báo/icon mới; HTML trỏ CSS/JS bằng hash nội dung mới. git diff --check đạt. Không chạy lại model/tìm kiếm hoặc bộ test nghiệp vụ vì chỉ đổi cách trình bày thông báo. Chưa xác nhận trực quan trên desktop/mobile; bước tiếp theo là tải lại trang #processing để xem thẻ mới.

## Animation frontend — 2026-10-10

- Theo yêu cầu chạy project, xác nhận server hiện còn chạy ở 127.0.0.1:8004 (PID 20432), trang chủ/motion.css/motion.js HTTP 200, dashboard native512 có 500 gallery approved và HTML dùng frontend animation mới. Dùng lại server đang hoạt động, không tạo thêm tiến trình hoặc truy vấn thử vào CSDL.
- Thêm frontend/static/motion.css và motion.js: nền cực quang/lưới/hạt nối theo con trỏ, vòng HSV/HOG/LBP, chữ đổi màu, menu/logo/nút chuyển động, xuất hiện theo cuộn và chuyển trang, nghiêng/phát sáng thẻ ảnh, tia sáng khi nhấn nút và có kết quả, quét khi tìm kiếm, biểu đồ mọc lên, hiệu ứng tiến độ xử lý. Giữ giao diện nền tối hiện có; app.css không bị ghi đè. Thay đổi template/app.js chỉ phục vụ trình bày, không đổi ảnh/vector, trọng số, cấu hình, model hay SQLite.
- Nút Animation nhớ lựa chọn qua localStorage, tôn trọng prefers-reduced-motion, dừng CSS/Canvas/Web Animations khi tab ẩn. Canvas giới hạn 30 fps, 54 hạt desktop/22 hạt mobile và DPR tối đa 1,5; không nghiêng theo chuột trên màn hình cảm ứng. Các lớp trang trí có pointer-events:none. Sửa lớp CSS ẩn hạng 4/5 ở màn hình trung bình; giữ đủ 5 thẻ và ảnh vuông trên mobile.
- HTML no-cache và URL CSS/JS có SHA-256 nội dung để tránh HTML/JavaScript lệch phiên bản do cache. Template có phiên bản dự phòng cho server cũ đang chạy. README bổ sung cách bật/tắt. Script verify_web_runtime kiểm tra thêm hai asset mới, phiên bản URL và header cache.
- Node --check đạt cho app.js/motion.js. Kiểm tra web trên bản sao SQLite đạt: trang chủ/bốn asset/dashboard HTTP 200; 500 ứng viên/5 ID duy nhất [80,216,31,586,520], history khớp, lỗi thiếu ảnh=422/thiếu history=404; chạy được ngoài cwd project. 10 tests tests/test_native512_processing.py đạt, còn cảnh báo deprecation TestClient/httpx đã có từ trước. git diff --check đạt. Không chạy lại model hoặc đánh giá chất lượng ảnh vì nhiệm vụ chỉ đổi giao diện.
- Lệnh dừng/khởi động lại server cũ và lệnh khởi chạy Chrome headless bị kiểm duyệt tự động chặn với lý do blocked by policy; không thực thi hai lệnh đó. Server mới đang chạy tại http://127.0.0.1:8004, server cũ http://127.0.0.1:8000 vẫn HTTP 200 và có asset mới. Browser Use không có surface khả dụng (apps/browsers rỗng). Chưa xác nhận trực quan animation/bố cục hoặc thao tác UI ở desktop/mobile; kiểm tra browser trực tiếp còn chờ. Chưa đo FPS thực tế; giới hạn 30 fps là cấu hình, không phải kết quả đo. Không ghi thêm truy vấn thử vào CSDL thật.

## Dọn bổ sung project — 2026-10-10

- Rà soát README, hợp đồng Repository/ProcessingJobs, dữ liệu DB, dependency editable và trạng thái tác vụ trước dọn. Tác vụ mới nhất completed, không có worker dataset chạy. Không xóa source code nghiệp vụ/test, ảnh gốc, mask/processed/query đang dùng, model/môi trường, Git, nguồn/giấy phép/duyệt ảnh, thống kê hoặc ZIP phục hồi.
- Xác định 43 file/394.054 byte dư: 28 cache Python trong backend/scripts/tests, 5 file metadata build egg-info (dist-info đã cài vẫn giữ), script tmp/verify_frontend_backend_layout.py lỗi thời đã được scripts/verify_web_runtime.py thay thế, và 9 log/trạng thái lần chạy thử cũ. Thư mục output rỗng cũng được dọn. Giữ ba file tác vụ mới nhất 7eff105151a940019191c817526d7672 và query-model.log.
- Lệnh Remove-Item đã bị kiểm duyệt tự động từ chối trước thực thi: blocked by policy. Chưa xóa vĩnh viễn/chưa giải phóng dung lượng. Thay vào đó chuyển nguyên các mục dư ra ../BTL_luu_tru_20261010/obsolete-after-project-cleanup; nhật ký/checksum docs/project-cleanup-20261010.json, moved=true/deleted=false.
- Đối chiếu sau chuyển: 725 file được bảo vệ giữ nguyên SHA-256; 43 file lưu trữ khớp checksum và không còn tại đường dẫn cũ. Chỉ sửa script cleanup_obsolete_data.ps1 trong phạm vi nhiệm vụ để thêm archive mới vào preview/purge thủ công, kiểm tra checksum/đường dẫn/không có link hoặc file ngoài kế hoạch. Distribution animal-face-cbir vẫn đọc được version 1.0.0; README/progress cập nhật trạng thái thật.
- CSDL trước/sau khớp: native512 600 ảnh/1800 vector, background512 5 ảnh/15 vector; cả hai integrity=ok, không lỗi FK, đường dẫn ảnh tồn tại. Trang chủ/CSS/JS/dashboard hai profile/processing API HTTP 200; processing vẫn giữ đúng tác vụ mới nhất completed, 5 cutout/5 ảnh đã nhập/5 gallery thử. Script cleanup chạy preview thành công, chưa chạy -Purge. git diff --check không lỗi whitespace; đa số code/file dự án đã là untracked từ trước, không stage/commit.
- Không chạy lại bộ test đặc trưng hoặc model vì không đổi thuật toán/ingestion/search. Chưa kiểm tra thao tác UI trên tab người dùng và chưa xử lý đủ 600 mask. Bước tiếp theo nếu cần giải phóng ổ đĩa: người dùng chạy scripts/cleanup_obsolete_data.ps1 để xem phạm vi, rồi -Purge để xóa năm thư mục dư đã liệt kê; bản ZIP phục hồi hiện hành không nằm trong phạm vi đó.

# Hiện hành: tính 512×512 và xử lý ảnh trên web — 2026-10-10

- Theo yêu cầu giữ ảnh 512 để tính: mặc định native512-v1, thêm background512-white-v1 cho nền trắng. Config/preprocess/SQLite riêng; baseline-v1 128 giữ nguyên công thức và số chiều. Chi tiết thuật toán ở features, schema ở database, giao tiếp ở contracts; không trộn config IDs hoặc preprocess khác nhau.
- Native512 đã nhập thật 600 ảnh/1800 vector, 500 gallery + 50 validation + 50 test. Tính lại đủ 1800 vector sai lệch lớn nhất 0; RGB nguồn 512 và checksum/pixel giữ nguyên; 0 trùng byte/pixel/dHash256 Hamming≤5, không group xuyên split, không candidate lỗi. Báo cáo: data/statistics/native512-v1/frontal512-verification.json. Thống kê thật: feature_summary.csv cùng thư mục. CSDL native512.db 445.591.552 byte sau nhập. Dùng ảnh nguồn trực tiếp làm processed khi pixel đã đúng để tránh nhân đôi ảnh.
- Lần nhập 512 đầu tiên bị CHECK width=128 từ schema cũ; đã sửa bằng migration 003, không sửa công thức để vượt kiểm tra. Migration rebuild giữ ID/metadata/vector/history, cho phép 128 hoặc 512. Đã kiểm chứng trên bản sao SQLite cũ 600 ảnh/1800 vector: dữ liệu giữ nguyên, integrity=ok, không lỗi FK, chạy lại idempotent đạt; sau đó nhập native512 thành công.
- Thêm DatasetProcessingService/ProcessingJobs, CLI process_dataset.py và trang Xử lý ảnh: chạy model, trích xuất/lưu SQLite, hoặc chạy cả hai bước; tiến độ, dừng, resume, xem cặp gốc/mask, phân trang và duyệt mask. UI gọi service; SQL trong Repository. Mask mới mặc định pending; không tự coi nguồn đã duyệt là mask đã đạt. Model ONNX giữ nguyên SHA-256 5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333 và môi trường riêng. Không thêm huấn luyện.
- Đã chạy thật 5 ảnh cat bằng model: RGBA 512, RGB khớp nguồn, alpha hợp lệ, 0 lỗi. Đã xem cả 5 mask, nhập 15 vector và duyệt 5 gallery thử; hình trước/sau artifacts/figures/native512/model-trial-review.png. Snapshot mask bất biến dưới background_removed/versions; file chỉnh tay dưới all-images. Chỉnh alpha rồi nhập lại tạo phiên bản mới và loại phiên bản cũ khỏi gallery nhưng giữ vector/ảnh cho lịch sử. Test sửa mask xác nhận chỉ một phiên bản active và dữ liệu cũ không bị thay đổi.
- Job web thử resume đầu tiên thất bại vì Windows chặn replace file tiến độ đang được đọc. Đã sửa sang tiến độ JSONL, đọc sự kiện hoàn chỉnh và bỏ phần đang ghi. Job web cuối 7eff105151a940019191c817526d7672 hoàn tất: 5 succeeded, nhập created=0/skipped=5/failed=0, 5 ảnh/15 vector, không sinh bản trùng và giữ trạng thái duyệt. Tính lại 15 vector nền trắng sau chuyển snapshot: sai lệch 0, integrity/FK đạt.
- Query PNG thường original/test/cat/pixabay_cat_003941.png nằm ngoài gallery đã tự tách nền bằng model, tính RGB 512, lưu query_id=1 và trả 5 ID duy nhất [4,1,3,2,5]; lịch sử khớp. Bằng chứng artifacts/evaluation/native512-background-smoke.json. Đây là kiểm tra tích hợp trên gallery thử 5 ảnh, không phải đánh giá chất lượng truy hồi toàn bộ.
- Kiểm tra code cuối: 50 pytest tests đạt (có cảnh báo deprecation từ Starlette/httpx); sau sửa cache preview mask, chạy lại 10 tests xử lý 512 đạt; Node kiểm tra cú pháp JS đạt. verify_web_runtime.py sau dọn dùng SQLite sao tạm: trang/assets/API đạt, 500 ứng viên → 5 ID duy nhất [80,216,31,586,520], lịch sử đúng, lỗi 422/404, chạy từ cwd ngoài project. Không sửa CSDL thật trong kiểm tra này.
- Browser Chrome headless: ba nút xử lý, 5 cặp ảnh preview 512, chọn profile native/background, chọn ảnh, trạng thái job completed; 0 lỗi JS và không tràn ngang ở desktop 1440/mobile 390. Đã xem screenshot và sửa màu nền/chữ trên card để đọc được. Ảnh chứng cứ artifacts/figures/native512/processing-ui.png và search-ui.png; script verify_native512_browser.mjs dùng Chrome DevTools đã khởi động. Server hiện chạy native512 tại http://127.0.0.1:8000, log tmp/web-server.stdout.log/stderr.log. Mở browser desktop tự động từng bị chặn, người dùng mở URL trực tiếp.
- Trước chuyển config, tạo ZIP phục hồi 600 ảnh nguồn + 600 ảnh xử lý 128, SQLite/metadata/query cũ: data/backups/before-native512-20261010.zip, 292.860.449 byte/1220 entries, SHA-256 02a01eb22e267b5bd9e8220a87ee1debbd3fe97f23c3206761eaabac5858b6ae. Đã kiểm tra CRC/hash, CSDL trong ZIP có 600 ảnh/1800 vector, integrity/FK đạt và đủ đường dẫn ảnh. Giữ ZIP này cùng JSON trong project.
- Dọn lần này: chuyển 1362 file/350388119 byte (runtime 128, báo cáo 128, ZIP mixed-20 cũ và SQLite backup dư và cache trình duyệt/test đã đóng) ra ../BTL_luu_tru_20261010/obsolete-after-native512. Không đụng 600 ảnh nguồn hiện hành, model, Git, môi trường hoặc thay đổi chưa commit. Nhật ký docs/native512-cleanup-20261010.json. Xóa vĩnh viễn bị kiểm duyệt tự động chặn trước đó (blocked by policy), vì vậy chỉ chuyển ra ngoài, chưa giải phóng dung lượng. cleanup_obsolete_data.ps1 chạy preview đạt checksum nguồn/ZIP và bốn phạm vi cố định; chưa chạy -Purge. Toàn bộ phạm vi preview hiện có 24306 file/18251521053 byte, gồm cả dữ liệu dư từ các lượt trước.
- Chưa kiểm tra/hoàn tất: chưa chạy model đủ 600 ảnh, profile nền trắng chỉ có 5 gallery thử nên chưa đủ 500 gallery nghiệm thu; chưa đánh giá đầy đủ P@5 cho 512 hoặc sau tách nền, chưa chấm Visual P@5/góc đầu/ID cá thể. Số liệu 128 cũ đã lưu trữ, không coi là kết quả 512. Chưa kiểm chứng cài mới trên môi trường sạch. Bước tiếp theo: trên Xử lý ảnh chọn toàn bộ và Chạy cả hai bước, xem/duyệt mask, đạt ít nhất 500 gallery tách nền rồi đánh giá validation/test tách biệt.

---

# Nhật ký trước thay đổi 512 (trạng thái tại thời điểm ghi)

## Chạy giao diện ngày 2026-10-10

- Khởi động Uvicorn ở chế độ baseline-v1, địa chỉ http://127.0.0.1:8000; log tại tmp/web-server.stdout.log và tmp/web-server.stderr.log. Trang chủ và dashboard HTTP 200; dashboard có 600 ảnh, 500 gallery, đủ ba config baseline.
- Lệnh mở trình duyệt tự động bị kiểm duyệt chặn với lý do blocked by policy. Server đang chạy; người dùng mở đường dẫn trực tiếp. Chưa kiểm tra thao tác qua trình duyệt trong lượt này; không thay mã ứng dụng/dataset.

## Thay bộ dữ liệu chính diện ngày 2026-10-10 — trạng thái trước đổi config 512

- Đối chiếu đề bài/requirements, contracts và code trước thay: đề không bắt buộc 20 loài. Chọn AFHQ v2 từ nguồn chính thức, tái sử dụng archive đã tải và xác minh checksum; không bịa URL/tác giả ảnh Flickr/Pixabay. Nguồn từng ảnh, thành viên ZIP, giấy phép CC BY-NC 4.0 và checksum tại data/manifests/frontal512_sources.csv (600 dòng); chi tiết docs/sources.md.
- Duyệt trực quan 1.560 ứng viên trên 44 bảng 220 px; xem lại bộ chọn ban đầu trên 24 bảng 256 px, loại thêm các ảnh quay/nghiêng/mờ/che khuất và bổ sung từ ứng viên đã duyệt. Quyết định ổn định lưu trong data/review/frontal512-20261010/decisions.json. Không đo góc đầu/tỷ lệ mặt bằng landmark. Phân bố sáu nhóm nhãn tại docs/dataset.md; fox không phải một loài đã xác minh.
- Runtime mới: 600 PNG RGB 512×512 giữ nguyên byte phát hành, 500 gallery + 50 validation + 50 test. Nguồn mới thay toàn bộ mixed-20; không phóng ảnh nhỏ thành ảnh lớn. Ảnh tính đặc trưng vẫn 128×128 theo preprocess-v1/baseline-v1, HSV/HOG/LBP giữ chiều 128/1764/160. Import tạo 600 ảnh/1.800 vector, skipped=0, failed=0; báo cáo frontal512_import.json.
- Sao lưu trước thay tại data/backups/before-frontal512-20261010.zip (93.992.131 byte, 1.447 mục) gồm SQLite, ảnh và metadata cũ. Đã kiểm tra SHA-256/CRC và trích SQLite tạm: 700 ảnh/2.100 vector, integrity=ok, không lỗi FK. Lần kiểm tra đầu gặp lỗi đóng kết nối SQLite trên Windows khi dọn thư mục tạm; đóng kết nối rõ ràng và chạy lại thành công.
- Kiểm tra CSDL staging trước thay: mọi ảnh/manifest/nguồn/SHA khớp; tái tiền xử lý pixel khớp, tái tính đủ 1.800 vector sai lệch tối đa 0; integrity=ok, không lỗi FK. Không trùng byte/pixel, không cặp dHash256 Hamming≤5 và không group xuyên split; 500 candidates, 0 rejected. Đã dùng SQLite backup API đưa bản đã kiểm tra vào app.db; không đổi schema/config.
- Sau khi chuyển file dư ra ngoài, chạy lại scripts/verify_frontal_dataset.py trên app.db hiện hành: toàn bộ kiểm tra trên vẫn đạt; báo cáo data/statistics/frontal512-verification.json mô tả CSDL đang chạy.
- API search/history baseline dùng nguồn 512×512 thay cho ảnh tính đặc trưng nhỏ; profile tách nền vẫn dùng processed nền trắng. SQL lấy đường dẫn theo lô nằm trong Repository, UI không tính đặc trưng riêng. Nhãn số nhóm trên giao diện lấy từ thống kê thay cho 20 cố định. Default manifest/công cụ import tách nền/contact sheet/duyệt đã đổi về snapshot mới.
- Kiểm tra 40 tests đạt. Kiểm tra web sau thay/dọn trên bản sao SQLite: trang chủ/assets/dashboard 200; hiển thị 6 nhóm, 500 ứng viên, 5 ID duy nhất, mọi ảnh kết quả RGB 512×512, history khớp ảnh/ID/thứ tự, lỗi 422/404; chạy được ngoài cwd project. AST Python và diff whitespace đạt; còn cảnh báo deprecation TestClient/httpx.
- Đánh giá thật: validation 50 query/9 cấu hình, test 50 query/5 cấu hình, đều 0 failed. Validation chọn HOG-only với P@5 theo nhãn=0,684. Test HSV=0,300; HOG=0,740; LBP=0,500; equal=0,436; selected=0,740. Đây là độ trùng nhóm nhãn, không phải accuracy/xác suất/Visual P@5; không so trực tiếp với mixed-20 cũ. App vẫn giữ mặc định trọng số 0,1/0,45/0,45. CSV/selected_weights tại data/evaluation, thống kê tại data/statistics.
- Demo thật dùng một query test ngoài gallery, HOG-only: 500 candidates/5 kết quả duy nhất, ghi query 1 và data/demo/latest_search.json, latest_top5.jpg. Không dùng query gallery để đánh giá.
- Dọn runtime: chuyển 1.740 file dư (317.890.538 byte) và cây thư mục rỗng sang ../BTL_luu_tru_20261010/obsolete-after-frontal512 và empty-after-frontal512. Ảnh nguồn/processed hiện còn đúng 600/600, một query lịch sử. Không đụng Git, môi trường, thay đổi của người khác hoặc model; checksum ONNX khớp. Thử tách nền cũ và DB thừa cũng rời runtime; chưa chạy model cho toàn bộ bộ mới.
- XÓA VĨNH VIỄN CHƯA THỰC HIỆN: kiểm duyệt tự động chặn lệnh xóa với lý do "blocked by policy". Chuyển ra ngoài không giải phóng ổ đĩa. Script scripts/cleanup_obsolete_data.ps1 đã chạy preview thành công, kiểm tra nguồn hiện hành/ZIP phục hồi và giới hạn ba thư mục dư: unused/data, obsolete-after-frontal512, empty-after-frontal512. Tổng đo hiện tại 17.901.132.934 byte; chỉ người dùng chạy -Purge để xóa. Nhật ký docs/frontal512-cleanup-20261010.json ghi rõ disposition; executed=false vì chưa xóa.
- Chưa kiểm tra browser trực tiếp, chưa đo landmark/ID cá thể, chưa chấm Visual P@5 hoặc chạy query thật thuộc nhóm ngoài gallery, chưa xử lý mask toàn bộ 600 ảnh. Bước tiếp theo: người dùng xem bảng duyệt cuối, mở giao diện thử ảnh mới và chạy script thủ công nếu muốn giải phóng dung lượng.

Các mục dưới đây là lịch sử tại thời điểm thực hiện; đường dẫn/số liệu cũ không mô tả snapshot đang chạy.

## Trích đặc trưng ảnh tách nền vào SQLite ngày 2026-10-10

- Thêm `scripts/import_background_dataset.py`: đối chiếu PNG với manifest/ảnh nguồn, yêu cầu đủ cutout mặc định, tạo manifest mới giữ nhãn/split/group/nguồn và nhập vector qua IngestionService/Repository vào SQLite riêng. Có cờ thử nghiệm --allow-partial; thiếu/sai ảnh dừng kèm đường dẫn. Ảnh mặc định pending cho đến khi duyệt mask; --reviewed kế thừa trạng thái đã duyệt của nguồn và cập nhật ảnh đã nhập. Nhập lại bỏ qua checksum trùng; sao lưu CSDL đích trước mỗi lần nhập lại. Bảo vệ app.db và manifest gốc.
- Thêm profile `background-white-v1` / `preprocess-bg-white-v1`, config tên hsv/hog/lbp-bg-white-v1, giữ số chiều 128/1764/160. Input PNG có alpha hợp lệ được ghép trắng rồi crop/resize. Cùng hàm tiền xử lý/version cho ingestion, search và evaluate; query thường bị từ chối BACKGROUND_REQUIRED. Processed của profile mới nằm trong thư mục riêng. Không thay schema hoặc ghi đè config cũ.
- AppConfig chọn profile qua CBIR_PROFILE; profile mới mặc định data/background_white.db và background_white_manifest.csv. HTTP adapter truyền đúng bundle và giao diện nhắc PNG đã tách nền/hiển thị profile đang chọn. Evaluate/demo dùng manifest và thư mục kết quả riêng. Khai báo httpx/httpcore cho kiểm tra web trong dependency và lock; uv pip check môi trường chính (66 gói) đạt.
- Thử thật 2 PNG đã xem mask tại data/background_removed/import-check-20261010/: nhập 2 ảnh/6 vector vào data/background_white_demo.db, integrity=ok; nhập lại created=0, skipped=2, số ảnh/vector không tăng. Tái tính 6 vector khớp tuyệt đối. Đây là bộ thử, không đủ 500 gallery và chưa phải CSDL mới để nghiệm thu. Báo cáo data/manifests/background_white_demo_manifest.import.json.
- Kiểm tra toàn bộ: 40 tests đạt (33 cũ + 7 mới), gồm nhập pending→reviewed, top 5 duy nhất, API chấp nhận đúng profile/từ chối query chưa tách nền, chặn CSDL/manifest gốc, thiếu cutout và không trộn config. Sau chỉnh nhãn giao diện/chuyển SQL kiểm tra vào Repository, chạy lại 7 test liên quan: đạt. API baseline trên bản sao thật vẫn có 500 ứng viên và 5 kết quả duy nhất; lịch sử/lỗi/asset đạt. Kiểm tra AST tất cả nguồn Python và diff whitespace đạt. Có cảnh báo deprecation httpx của Starlette, chưa đổi TestClient backend.
- Checksum 1.402 file ảnh/data được CSDL gốc tham chiếu giữ nguyên; hash nội dung logic app.db giữ nguyên (700 ảnh/2.100 vector cũ). Snapshot trước dọn vẫn được giữ.
- Hướng dẫn lệnh thực thi: docs/background-import.md; contracts/features/dataset/database và README đã cập nhật. Chưa tách/nhập toàn bộ 700 ảnh hoặc mở browser với dữ liệu mới; chưa đo chất lượng truy hồi sau tách nền. Bước tiếp theo: chạy model đủ bộ, nhập vector, duyệt mask, cho phép gallery đã duyệt rồi đánh giá bằng query tách biệt.

## Khôi phục công cụ tách nền ngày 2026-10-10

- Đưa `birefnet-general-lite.onnx` về `animal_face_model/`, giữ bản model trong thư mục lưu trữ; SHA-256 khớp `5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333`, kích thước 224.005.088 byte. Chuyển môi trường Python riêng từ bản lưu trữ về `.venv` của thư mục model; bổ sung rembg 2.0.67 và ONNX Runtime 1.31.0. `uv pip check` kiểm tra 50 gói: không xung đột.
- Thêm `animal_face_model/remove_background.py`: dùng model cục bộ kiểm tra checksum, CPU 4 luồng mặc định, xử lý một ảnh hoặc thư mục con, xuất RGBA giữ kích thước sau EXIF và nguyên pixel RGB, ghi báo cáo checksum/alpha/lỗi, exit code khác 0 khi có ảnh lỗi. Không ghi đè đầu ra có sẵn hoặc ghi vào các thư mục ảnh runtime được bảo vệ. README, requirements và setup.ps1 của model có hướng dẫn; .gitignore bỏ qua model, môi trường và đầu ra tách nền.
- Chạy thật 2 ảnh cat AFHQ: 2 thành công, 0 lỗi, RGBA 512×512, alpha 0..255, RGB khớp nguồn. Đã xem hai preview nền trắng; nền được loại và vùng mặt chính được giữ trong hai mẫu. Ảnh thử/báo cáo tại `data/background_removed/restore-check-20261010/`. Kiểm tra chặn ghi vào original và chặn đầu ra trùng đều đạt (lệnh dừng trước xử lý).
- Kiểm tra checksum 1.424 file được bảo vệ theo nhật ký dọn: giữ nguyên; hash nội dung logic CSDL giữ nguyên. Không đổi mã nghiệp vụ web hoặc feature config nên không chạy lại bộ test baseline trong lượt này.
- Công cụ xử lý riêng đã chạy được; chưa xử lý toàn bộ 700 ảnh, chưa tích hợp tách nền vào truy hồi hoặc đo chất lượng mask/Visual P@5 trên các loài khác. Bước tiếp theo: duyệt mask trên mẫu nhiều loài; nếu áp dụng vào truy hồi phải tạo config/preprocess mới, xử lý gallery và query cùng pipeline rồi tính lại vector theo cấu hình mới.

## Kiểm tra đồng bộ ngày 2026-10-10

- Kết luận: luồng chạy trên môi trường hiện có đồng bộ về mã nguồn, API, CSDL, ảnh và vector; chưa xác nhận khả năng dựng mới hoàn chỉnh hoặc chất lượng nghiệm thu toàn bộ ảnh.
- Kiểm tra read-only 700 ảnh: manifest khớp đường dẫn, split, group_id, trạng thái, nguồn/giấy phép và nhãn đã chuẩn hóa; hash ảnh gốc khớp; tái xử lý ảnh RGB 128×128 khớp pixel/hash. Tính lại đủ 2.100 vector bằng pipeline hiện tại, sai lệch tuyệt đối lớn nhất 0; config HSV/HOG/LBP khớp tên, ID ánh xạ, chiều, tham số và preprocess-v1. Không có group_id xuyên split; hai lịch sử truy vấn có ảnh và 5 kết quả duy nhất. Nội dung CSDL không đổi.
- Schema hiện hành khớp 26 đối tượng schema tạo từ migrations 001/002 trên CSDL tạm; integrity_check=ok, không lỗi khóa ngoại. Frontend dùng đúng ba API search/dashboard/history; 47 ID DOM được gọi tĩnh đều có trong template.
- Chạy lại 33 tests: đạt. Kiểm tra web trên bản sao CSDL: trang chủ/assets/dashboard 200, tìm từ 500 ứng viên trả 5 ID duy nhất, lịch sử đúng thứ tự, lỗi đầu vào/history 422/404. Chưa mở trình duyệt trực tiếp.
- Thư viện khai báo và các phiên bản trong requirements.lock đều khớp môi trường đang cài; không thiếu phụ thuộc bắt buộc của các gói đã khóa. Tuy nhiên `scripts/verify_web_runtime.py` dùng TestClient/httpx 0.28.1 mà pyproject, requirements.txt và requirements.lock chưa khai báo httpx. Chưa dựng thử môi trường sạch. Không đổi dependency hoặc cài thư viện trong lượt rà soát này.
- Sửa lỗi mã hóa tiếng Việt do thao tác ghi ở lượt dọn trước trong README và phần mới của progress/sources; cập nhật đường dẫn lưu trữ trong architecture/dataset/database/sources. Phân biệt metadata search_config đã triển khai với metadata phiên bản/snapshot/môi trường còn thiếu; không sửa schema hoặc mã nghiệp vụ.
- Bằng chứng máy đọc: `docs/sync-audit-20261010.json`. Bước tiếp theo: khai báo phụ thuộc kiểm tra web và kiểm chứng dựng mới; thử giao diện trong trình duyệt. Yêu cầu chất lượng ảnh chính diện, Visual P@5 và metadata tái lập lịch sử vẫn cần xử lý riêng theo tiến độ hiện hành.
## Dọn project ngày 2026-10-10

- Đối chiếu đường dẫn CSDL và phụ thuộc runtime trước dọn; sao lưu SQLite hiện tại tại `data/backups/runtime-before-cleanup-20261010/app.db`.
- Chuyển 702 mục (673 mục tài liệu/ảnh cũ và 29 nhóm dữ liệu/cache dư) sang thư mục cạnh project `../BTL_luu_tru_20261010/`. Các nhóm dự kiến xóa chứa 19.525.753.111 byte; **chưa xóa vĩnh viễn, chưa giải phóng dung lượng ổ đĩa** vì kiểm duyệt tự động chặn lệnh xóa hàng loạt. Nhóm dư nằm trong `unused/` của bản lưu trữ.
- Giữ 700 ảnh đang dùng, 500 gallery, 2 ảnh của lịch sử truy vấn, 2.100 vector, `.venv`, Python nền `tmp/uv-python`, Git, mã nguồn và công cụ kiểm tra. Tài liệu/báo cáo/model cũ được lưu ngoài project. Các đường dẫn download/review/replacements/artifacts trong các mục lịch sử bên dưới không còn là vị trí hiện hành.
- Chuyển helper kiểm tra web thành `scripts/verify_web_runtime.py`; đóng rõ các kết nối SQLite sao lưu để thư mục tạm dọn được trên Windows. Cập nhật README theo cấu trúc sau dọn.
- Kiểm tra: 33 tests đạt; API trên bản sao CSDL đạt (trang chủ/CSS/JS/dashboard 200, 500 ứng viên, 5 ID duy nhất, lịch sử đúng thứ tự, lỗi 422/404). Checksum của 1.424 file được bảo vệ giữ nguyên; hash nội dung logic CSDL giữ nguyên, integrity_check=ok, không lỗi khóa ngoại, bản sao CSDL integrity_check=ok. Nhật ký `docs/cleanup-20261010.json`.
- Chưa kiểm tra trình duyệt trực tiếp hoặc đánh giá lại chất lượng ảnh; gallery không thay đổi. Bước tiếp theo nếu cần giải phóng ổ đĩa: người dùng xóa thư mục `unused/` trong bản lưu trữ sau khi đối chiếu nhật ký.
# Trạng thái hiện tại và bàn giao

Cập nhật: 2026-10-10.

## Tải bộ ảnh mặt động vật chất lượng hơn ngày 2026-10-10

- Tìm các bộ nguồn công khai trên web, xác minh nguồn tác giả/giấy phép; tải đầy đủ AFHQ v2 (15.803 PNG 512×512, khoảng 6,96 GB) và CatFLW v2 (2.079 PNG cùng nhãn khuôn mặt, khoảng 1,45 GB). Nguồn/README/NOTICE/metadata/checksum lưu trong `data/downloads/hq-faces-20261010/`; không coi bản v2 của cùng cảnh AFHQ là query độc lập.
- Archive Mandrillus đầy đủ tải rất chậm nên chuyển sang tải đúng thành viên ZIP nguồn bằng HTTP Range: 373 ảnh màu thuộc 373 cá thể, FaceQual=3/FaceView=1, giữ byte nguồn; xác minh CRC/kích thước từng thành viên và MD5 metadata công bố. Đóng gói `mandrillus-quality3-front-color.zip`. Chưa tải hoàn tất archive gốc 29.495 ảnh; phần `.part`/`.chunks` giữ riêng, không tính vào bàn giao hoàn tất.
- Nhãn Mandrillus không bảo đảm chất lượng trực quan: trong mẫu vẫn có ảnh xa với bảng màu, tối, nhắm mắt, nghiêng hoặc che miệng. Xem 5 bảng đầy đủ gồm 180 ảnh, chọn và xem lại 50 ảnh màu, mặt lớn gần chính diện, mắt–mũi–miệng rõ trên hai bảng cuối; đóng gói `mandrillus-visual-selected-50.zip`, đủ 50 cá thể riêng, RGB 224×224, giữ SHA-256 nguồn, ZIP CRC đạt. Không đo góc bằng landmark.
- Kiểm tra tải: kích thước AFHQ/CatFLW khớp, ZIP CRC đạt, có SHA-256 cục bộ; metadata Zenodo khớp MD5 nguồn. Giải nén và giải mã đủ 18.255 tệp ảnh, 0 lỗi. AFHQ có 2 ảnh xám/gần xám và 1 nhóm trùng byte; CatFLW có 54 ảnh xám/gần xám và 8 nhóm trùng byte; bộ 373 Mandrillus không xám/trùng byte. Mandrillus thực tế có 361 ảnh 224×224, 7 ảnh 224×223 và 5 ảnh 224×148, không giả định mọi ảnh đúng kích thước công bố.
- Xuất catalog và danh sách pending: AFHQ 15.800 ảnh màu duy nhất theo SHA-256; CatFLW 1.016 ảnh màu duy nhất có cạnh ngắn vùng mặt ≥256 px, cả 2.079 bounding box tồn tại và nằm trong ảnh. Đã xem mẫu AFHQ cat/dog/wild màu và CatFLW crop; nguồn vẫn có ảnh nghiêng/tối cần duyệt. Bằng chứng: `data/review/hq-faces-20261010/verification.json` và kiểm tra riêng bộ 50.
- Thêm các script tải/giải nén/duyệt/đóng gói; kiểm tra cú pháp chạy đạt, các script đã thực thi trên dữ liệu tải thật. Không đổi mã ứng dụng, pipeline, manifest gallery hoặc DB; không chạy lại unit test của ứng dụng. Chưa duyệt hết nguồn, chưa gán loài AFHQ wild, chưa kiểm tra gần trùng/rò rỉ xuyên nguồn với gallery/query hoặc đánh giá truy hồi. Bước tiếp theo: chọn/crop ảnh cho snapshot mới, kiểm tra trùng và chia split trước khi nhập. So sánh nguồn/giới hạn ở `docs/hq-face-datasets-20261010.md`.

## Tìm ảnh thay thế ngày 2026-10-10

- Đã sàng lọc ảnh chưa dùng từ archive AFHQ/AFD, loại source member bị rejection và nhóm nguồn query; xem 10 contact sheet ứng viên. Tìm bổ sung trên Wikimedia Commons, tải ảnh thật và lưu metadata nguồn/giấy phép; một số ảnh Commons không được chọn vì góc nghiêng, mờ, nhiều mặt hoặc taxonomy mâu thuẫn. Các lần tải trả HTTP 429 được ghi nhận; dùng thumbnail ở kích thước Wikimedia hỗ trợ cho các nguồn cần thiết, không mô tả thumbnail là file gốc lớn nhất.
- Chọn 12 ảnh đề xuất thay cho gallery ID 45, 109, 130, 161, 176, 337, 386, 437, 456, 478, 599 và 683: 7 AFHQ/AFD, 5 Commons. Đã xem ảnh nguồn được chọn và hai bảng ảnh trước–sau crop; mặt gần chính diện, mắt/mũi/miệng đủ quan sát. Chưa xác minh góc quay/tỷ lệ mặt bằng landmark; không tuyên bố đã tìm hết ảnh kém còn lại.
- Bộ bàn giao: `data/replacements/20261010/` gồm ảnh nguồn, PNG RGB 128×128, bảng ánh xạ, manifest 12 dòng và manifest đề xuất 700 dòng, attribution, vector thử và verification. Pipeline preprocess-v1 và baseline-v1 giữ nguyên; trích thử 36 vector đúng chiều và hữu hạn. Kiểm tra SHA-256 gốc/pixel không trùng, dHash 256 bit Hamming ≤5 không phát hiện cặp mới–hiện tại/mới–mới; không tái dùng rejection hoặc group_id query. Manifest đề xuất vẫn 500/100/100, số ảnh từng loại giữ nguyên.
- Đóng gói `output/datasets/anh_thay_the_20261010.zip` gồm 33 tệp. Kiểm tra CRC ZIP, tồn tại đường dẫn ảnh, 700 đường dẫn duy nhất trong manifest đề xuất và phân bố từng loại/split so với manifest chính thức đều đạt.
- `approved` chỉ gán trong bộ đề xuất sau duyệt 12 ảnh, không cập nhật DB/runtime. Không thay ảnh/manifest/vector hiện hành, không chạy lại unit test do không sửa ứng dụng. Bước tiếp theo nếu áp dụng bộ đề xuất: backup DB, thay metadata/processed/vector đúng ánh xạ, giữ ảnh cũ và tái chạy kiểm tra/đánh giá; các số P@5 cũ không đại diện snapshot mới. Nguồn được ghi tại `docs/sources.md` và attribution của bộ đề xuất.

## Rà soát bộ ảnh theo đề Word ngày 2026-10-10

- Đã đọc đầy đủ đề `Xây dựng hệ CSDL lưu trữ và tìm kiếm ảnh mặt động vật.docx`, đối chiếu tài liệu dữ liệu và pipeline. Kết luận: đạt kiểm tra kỹ thuật nhưng chưa bảo đảm 500 gallery đều chụp thẳng, mặt ở giữa và có tỷ lệ chủ thể tương đồng theo đề. Các trạng thái hoàn thành/approved trước đây không thay thế kết luận chất lượng trực quan lần này.
- Kiểm tra read-only cả 700 ảnh gốc/processed: giải mã, checksum và tái lập pixel bằng pipeline đạt; processed đều RGB 128×128; 2.100 vector đúng chiều và hữu hạn; không thiếu bundle; integrity_check=ok, không lỗi khóa ngoại. Manifest khớp tập đường dẫn DB; không trùng hash gốc/pixel, không có group_id xuyên split; dHash 256-bit Hamming ≤5 kiểm tra mọi cặp kể cả khác loại cho 0 cặp.
- Đã xem đủ 14 contact sheet mới từ ảnh processed hiện hành và montage 16 ảnh gốc minh họa. Ghi nhận 12 ví dụ gallery cần thay/duyệt lại, gồm góc quay/ngửa đầu, che miệng, crop sát và mờ; không dùng 12 làm số đếm đầy đủ ảnh không đạt. Gallery chỉ đúng 500 nên cần bổ sung/thay ảnh trước khi loại. Query khó được ghi riêng, không tự coi là vi phạm yêu cầu đầu vào mới.
- Chi tiết, giới hạn và bước tiếp theo tại `docs/dataset-review-20261010.md`; bằng chứng tại `artifacts/dataset-review-20261010/`. Không đổi ảnh, manifest, vector, CSDL hoặc mã ứng dụng; không chạy lại unit test. Chưa chấm từng ảnh bằng rubric đầy đủ, đo landmark/tỷ lệ mặt hoặc đánh giá lại truy hồi; bước tiếp theo là duyệt danh sách thay ảnh và tái tính/đánh giá sau khi đổi snapshot.

## Tách thư mục frontend/backend ngày 2026-10-06

- Chuyển templates, static và design-system vào `frontend/`; chuyển `app.py` và `src/` vào `backend/`. Cập nhật import của scripts/tests sang `backend.src`, vị trí frontend assets và cách xác định gốc BTL trong AppConfig. Dữ liệu, migrations, scripts, tests và cấu hình môi trường tiếp tục nằm ở gốc.
- Lệnh chạy hiện tại: `.venv\Scripts\python.exe -m uvicorn backend.app:app --reload`. Hai phần vẫn dùng chung một server Starlette; đường dẫn và nội dung HTTP API giữ nguyên. README, architecture, đường dẫn model trong contracts và script nguồn báo cáo đã cập nhật.
- Đã kiểm tra: 33 tests passed; tất cả nguồn Python đọc được bằng AST; cài editable package từ gốc BTL thành công; entry point Uvicorn nạp được; CLI evaluate/import hiển thị help thành công với `-X utf8`. Lần thử help đầu gặp encoding console cp1252, chạy lại ở chế độ UTF-8 đạt.
- Kiểm tra HTTP bằng TestClient trên bản sao SQLite và 500 ảnh gallery: trang chủ, CSS, JS, dashboard trả 200; tìm kiếm có 500 ứng viên và 5 ID duy nhất; lịch sử giữ đúng thứ tự; ảnh thiếu trả 422, lịch sử không tồn tại trả 404. Kiểm tra đạt cả khi thư mục làm việc nằm ngoài BTL. CSDL thật chỉ được mở read-only để sao lưu; truy vấn thử được lưu trên bản sao tạm.
- Đã xem diff đối chiếu bản trước chuyển; nội dung frontend assets giữ nguyên. Bản đối chiếu nằm tại `tmp/frontend-backend-before-20261006/`; script kiểm tra tích hợp tại `tmp/verify_frontend_backend_layout.py`. TestClient cảnh báo deprecation của httpx; kiểm tra vẫn đạt.
- Chưa kiểm tra giao diện trực tiếp trong trình duyệt và chưa tái xuất PDF. Bước tiếp theo: chạy lệnh mới ở gốc BTL, mở `http://127.0.0.1:8000` để kiểm tra thao tác upload/crop trên trình duyệt.

## Bàn giao model tách nền ngày 2026-10-03

- Theo phạm vi người dùng xác nhận, chỉ bàn giao model pretrained `animal_face_model/birefnet-general-lite.onnx` để người dùng tự chạy; hướng dẫn trong README cùng thư mục.
- Đã xác minh checksum và thử CPU trên 20 ảnh mẫu thuộc 20 loại. Chưa tách toàn bộ dataset và chưa đánh giá truy hồi sau tách nền.
- Đã hoàn lại các thay đổi tích hợp tách nền vào ứng dụng; 33 kiểm thử hiện có đạt. Ảnh gốc, vector và database đang chạy giữ nguyên.

## Rà soát và ba báo cáo PDF ngày 2026-09-30

- Bìa báo cáo theo xác nhận: Phạm Huy Hoàng, B23DCCN343, môn Cơ sở dữ liệu đa phương tiện; nội dung bám đề bài DOCX.
- Đã tạo `output/pdf/01_Bao_cao_Phan_1_2.pdf` (14 trang), `02_Bao_cao_Phan_3_4.pdf` (19 trang), `03_Bao_cao_BTL_Hoan_chinh.pdf` (32 trang).
- Đã sửa cache khi vector bị UPDATE mà số dòng không đổi, nhận lại ảnh khi khôi phục tệp; thêm migration 002 và snapshot backup trước nâng cấp.
- Đã sửa chuẩn hóa trọng số lớn và xử lý đường dẫn gallery sai; 33 tests đạt.
- Tái kiểm 100 query selected: đúng toàn bộ ID/thứ tự top 5; sai lệch score tối đa 2,22e-16. API tìm kiếm/lịch sử/lỗi đã kiểm tra trên bản sao dữ liệu thật.
- Phân tích bổ sung và hình thật ở `artifacts/report-evidence/`; kế hoạch cải tiến và giới hạn chi tiết ở `docs/project-review.md`.
- Rà soát ảnh mẫu phát hiện còn góc nghiêng/che mặt, ví dụ ID 386 và 456. 500 ảnh hợp lệ về kỹ thuật không đồng nghĩa 500 ảnh đạt chính diện tuyệt đối.
- Visual P@5 vẫn chưa có người chấm; tập unknown riêng và browser demo chưa được kiểm chứng. Công cụ điều khiển browser không có phiên khả dụng.

## Cập nhật giao diện ngày 2026-09-30

- Đã thay giao diện Streamlit bằng ứng dụng web Starlette một tiến trình, giữ nguyên `SearchService`, `Repository` và pipeline CBIR.
- Giao diện mới có upload kéo-thả, crop vuông có xem trước, điều chỉnh trọng số, top 5, giải thích đóng góp điểm, đặc trưng trung gian, sức khỏe dữ liệu, lịch sử và trang phương pháp.
- Design system FaunaFind được sinh bằng UI UX Pro Max và lưu tại `design-system/faunafind/MASTER.md`.
- Lệnh chạy mới: `.venv\Scripts\python.exe -m uvicorn app:app --reload`.

## Trạng thái trung thực

Baseline ứng dụng, dữ liệu, SQLite, trích đặc trưng, tìm kiếm, kiểm thử và đánh giá theo nhãn đã chạy thành công. Ba báo cáo PDF đã được soạn theo yêu cầu; Visual P@5 vẫn cần người chấm độc lập.

| Hạng mục | Trạng thái | Bằng chứng |
| --- | --- | --- |
| 500 gallery | Hoàn thành | `mixed_20_manifest.csv`, contact sheet, `data/app.db` |
| 100 validation + 100 test | Hoàn thành | Mỗi split có 5 ảnh cho từng loại |
| Duyệt chất lượng | Hoàn thành | 1.258 source member bị loại và khóa ổn định |
| HSV/HOG/LBP | Hoàn thành | 700 vector cho mỗi config, tổng 2.100 |
| SQLite | Hoàn thành | FK/UNIQUE/CHECK, transaction, integrity `ok` |
| Search top 5 | Hoàn thành | 500 ứng viên, không lọc theo nhãn |
| Demo | Hoàn thành | `data/demo/latest_search.json`, `latest_top5.jpg` |
| Đánh giá nhãn | Hoàn thành | `data/evaluation/metrics_*.csv` |
| Visual P@5 | Chưa chấm | `judgments_template.csv` là mẫu rỗng |
| Ba báo cáo PDF | Đã tạo | `output/pdf/`, script tái tạo và dữ liệu bằng chứng |

## Snapshot chính thức

- Manifest: `data/manifests/mixed_20_manifest.csv`.
- Database: `data/app.db`.
- 20 loại; mỗi loại có 25 gallery, 5 validation, 5 test.
- Tổng 700 ảnh `approved`, trong đó 500 candidate gallery.
- AFHQ cung cấp cat/dog; AFD cung cấp 18 loại còn lại.
- Backup snapshot AFHQ cũ: `data/backups/2026-09-28-afhq-three-domain/`.

Kết quả xác minh cuối:

```text
integrity=ok
splits=[('gallery', 500), ('test', 100), ('validation', 100)]
types=20
gallery_per_type=(25, 25)
features=[('HSV', 128, 700), ('HOG', 1764, 700), ('LBP', 160, 700)]
missing_features=0
duplicate_hashes=0
near_duplicate_pairs=0
cross_split_near_duplicate_pairs=0
```

## Đánh giá cuối

Validation chọn `HSV=0,10; HOG=0,45; LBP=0,45`. Mỗi split có 100 query hợp lệ, 0 lỗi.

| Run | Validation Same-species P@5 | Test Same-species P@5 |
| --- | ---: | ---: |
| HSV | 0,206 | 0,274 |
| HOG | 0,316 | 0,298 |
| LBP | 0,272 | 0,292 |
| Equal | 0,300 | 0,314 |
| Selected | **0,414** | **0,368** |

Median latency của cấu hình selected trên test là 69,13 ms; p95 là 116,56 ms trong script đánh giá. Đây là label agreement, không phải Visual P@5 hoặc xác suất.

Demo cuối dùng query `Panthera leo` ngoài gallery và trả 5/5 kết quả cùng loài từ toàn bộ 500 candidate.

## Công việc đã thực hiện ngày 2026-09-28

- Tải/xác minh 18 archive AFD chính thức từ Mendeley và ghép với cat/dog AFHQ.
- Sửa chia split để lọc rejection trước khi cấp phát và tối đa hóa số identity query trong giới hạn dung lượng.
- Duyệt nhiều vòng; chặn 1.258 ảnh nguồn bị mờ, tối, che khuất, sai góc hoặc thiếu mặt.
- Sửa đánh giá để so nhãn không phân biệt hoa/thường và dùng `relative_path` làm khóa query duy nhất.
- Xây lại manifest 700 ảnh, processed images, 2.100 vector và SQLite.
- Chạy lại kiểm tra gần trùng, thống kê, validation, test và demo sau lần thay ảnh cuối.
- Giữ nguyên backup AFHQ cũ trước khi thay database.

## Hoàn thiện báo cáo và dọn project ngày 2026-09-30

- Xuất lại ba báo cáo PDF: nền trắng, chữ đen; bảng, sơ đồ và biểu đồ thống kê dùng đen trắng. Ảnh dữ liệu và logo giữ màu gốc.
- Dàn lại toàn bộ công thức bằng kiểu chữ toán STIX: phân số, căn, tổng có cận, chỉ số, vector và chuẩn L2; các phép tính dài được căn giữa trên hai dòng.
- Loại bỏ các nội dung dẫn chiếu không cần thiết theo yêu cầu; giữ nguồn kỹ thuật và nguồn dữ liệu phục vụ kiểm chứng.
- Gỡ `src/visualization.py` không có nơi gọi và khai báo phụ thuộc Plotly; dọn bản sao tài liệu dư, cache và tệp tạm vào Thùng rác.
- Giữ môi trường Python, dữ liệu đang sử dụng, bản sao lưu và công cụ tái lập báo cáo.
- Sau khi dọn, 33 kiểm thử đạt. Kiểm tra màu chữ, màu nền và nội dung bằng PyMuPDF; xem ảnh dựng của toàn bộ 65 trang, không phát hiện lỗi bố cục.
- Kết quả kiểm tra tại `artifacts/report-evidence/pdf-qa.json`; nhật ký dọn tại `artifacts/report-evidence/cleanup-log.json`.
- Đợt dọn cuối loại bỏ cache Python, snapshot cat/dog cũ không còn được tham chiếu, ảnh giao diện trung gian, thư mục công cụ thiết kế đã hoàn tất vai trò và các đầu vào PDF không còn sử dụng. Giữ dữ liệu tái lập, hai backup đang được tài liệu dẫn chiếu, môi trường chạy và ba PDF bàn giao.

## Việc còn lại

1. Hai người chấm độc lập Visual P@5 nếu môn học yêu cầu.
2. Rà soát lại chất lượng chính diện/che khuất, thay mẫu kém và tái đánh giá nếu đổi snapshot.
3. Chạy demo trên máy trình bày và chuẩn bị video dự phòng nếu cần.

Không cần tải database khác: file SQLite dùng để nộp/chạy là `data/app.db`. DB Browser for SQLite chỉ là phần mềm mở file này.

## Sắp xếp cấu trúc ngày 2026-10-04

- Đưa mã nguồn, data, scripts, tests, docs, giao diện, migrations, artifacts và môi trường Python trực tiếp về gốc BTL; output và tmp cũng nằm trong BTL.
- Cập nhật đường dẫn báo cáo thành output/pdf tính từ gốc dự án và gộp quy tắc .gitignore.
- Giữ kho Git của BTL tại chỗ. Thư mục animal-face-image-retrieval ở bên ngoài chỉ còn .git và .gitignore để bảo toàn lịch sử Git riêng; thao tác chuyển .git đã bị bộ kiểm duyệt tự động từ chối.
- Kiểm tra sau chuyển: 33 tests passed; import ứng dụng, đường dẫn dự án, ba PDF, cú pháp script báo cáo và SQLite quick_check đều đạt. Không tái xuất PDF hoặc thử giao diện trình duyệt trong lần sắp xếp này.

## Chuyển tài liệu IoT sang LaTeX ngày 2026-10-05

- Theo yêu cầu riêng của người dùng, chuyển `CHƯƠNG 5 IOT.docx` sang `output/latex/iot_chapter5/chuong5.tex`; gói bàn giao gồm nguồn, hai ảnh đồ thị và hướng dẫn ở `output/latex/chuong5_latex.zip`.
- Đối chiếu 427 đoạn có văn bản, 13 ảnh và 1 công thức Word; gõ lại 7 ảnh công thức, ảnh ba chuỗi nhị phân và dựng lại hai sơ đồ bằng LaTeX/TikZ. Giữ nguyên mã ví dụ và nội dung còn thiếu của bản gốc.
- Kiểm tra độ bao phủ đoạn, ngoặc/môi trường LaTeX, tệp ảnh và tính toàn vẹn ZIP đạt. Trình biên dịch tích hợp lỗi môi trường `Unable to find standard directories for platform`; chưa xác minh PDF/bố cục, chưa chạy mã Python minh họa. Cần biên dịch gói trên Overleaf hoặc TeX Live để kiểm tra trang.


## Chỉnh sửa chương IoT theo hai PDF ngày 2026-10-05

- Đọc PDF tiếng Việt 35 trang và đối chiếu toàn bộ Chương 5 sách gốc, trang PDF 151–184. Sửa trực tiếp `output/latex/iot_chapter5/chuong5.tex`, giữ trình soạn thảo hiện tại.
- Bỏ lưu ý/ghi chú bổ sung của bản dịch, giải thích nhãn/code ngoài nội dung nguồn và đầu/chân trang. Bổ sung các mục thuật toán di truyền, chọn lọc, lai ghép, đột biến, ưu/nhược điểm, DEAP, hình nguyên phân/giảm phân/lai ghép và công thức mô phỏng tôi luyện; khôi phục thụt lề/xuống dòng code từ PDF, giữ API và logic nguồn.
- Văn bản thường dùng Times New Roman 13 pt; gói LaTeX kèm font và hình, cần XeLaTeX. Cập nhật `output/latex/chuong5_latex.zip`.
- Tạo bản PDF chỉnh sửa riêng tại `output/pdf/Chuong_05_Thuat_toan_di_truyen_cho_IoT_Tieng_Viet_da_sua.pdf` (27 trang); giữ nguyên hai PDF đầu vào. Đã xem ảnh dựng toàn bộ 27 trang, kiểm tra font/size, không còn chữ chân trang/ghi chú đã loại và không có span tràn lề. Kiểm tra cấu trúc nguồn, tài nguyên, ZIP và cú pháp 24 khối Python đạt; không chạy ví dụ huấn luyện.
- Trình biên dịch LaTeX tích hợp tiếp tục báo lỗi môi trường `Unable to find standard directories for platform`; chưa xác minh PDF do XeLaTeX biên dịch. PDF bàn giao được dàn trang riêng từ cùng nội dung đã làm sạch. Cần chạy XeLaTeX nếu muốn xác minh bố cục xuất từ nguồn LaTeX.

## PowerPoint thuật toán di truyền cho IoT ngày 2026-10-05

- Tạo `output/presentations/Thuat_toan_di_truyen_cho_IoT.pptx`: 24 slide tỷ lệ 16:9 theo PDF tiếng Việt 27 trang người dùng chỉ định, kèm ghi chú thuyết trình và nguồn trang cho từng slide.
- Nội dung gồm tối ưu hóa, cơ chế GA, DEAP, đoán từ, tìm kiến trúc CNN và tối ưu LSTM. Có 6 bảng và 1 biểu đồ chỉnh sửa được, dữ liệu biểu đồ đúng chuỗi fitness tài liệu báo cáo; hình bìa minh họa do công cụ tạo ảnh tích hợp tạo.
- Kiểm tra cấu trúc PPTX, số slide, font, hình học bố cục, bảng và dữ liệu biểu đồ đạt, không có finding/warning. Đã dựng và xem toàn bộ slide, sửa hướng mũi tên/quy trình GA, tái nhập file cuối và dựng đủ 24 slide; 22 ảnh trùng bản đã duyệt, 2 ảnh khác đã xem lại đạt.
- Chưa mở trực tiếp trong Microsoft PowerPoint và chưa chạy lại các ví dụ GA/CNN/LSTM. Bước tiếp theo: mở file trên máy trình bày và thêm thông tin nhóm nếu cần.

## Chỉnh phong cách PowerPoint IoT ngày 2026-10-05

- Theo phản hồi người dùng, tạo `output/presentations/Thuat_toan_di_truyen_cho_IoT_ban_day_du.pptx`, giữ 24 slide nhưng tăng nội dung giải thích, dùng nền trắng, tiêu đề xanh đậm và danh sách câu đầy đủ theo kiểu báo cáo môn học; bỏ hình bìa AI và chữ/số phóng lớn.
- Giữ ghi chú thuyết trình, nguồn PDF, các sơ đồ phục vụ giải thích, 5 bảng và biểu đồ có dữ liệu chỉnh sửa được. Đã sửa chỗ sát/đè nội dung ở slide 13, 15 và 23.
- Kiểm tra gói PPTX, số trang, font, gạch đầu dòng, bảng và dữ liệu biểu đồ đạt. Đã xem toàn bộ 24 slide, tái nhập và dựng file cuối; 20 ảnh trùng bản duyệt, 4 ảnh khác đã kiểm tra lại. Có 1 cảnh báo ước lượng chiều cao bảng ở slide 10; hình dựng cho thấy bảng và dòng chú thích không chồng nhau.
- Chưa mở trực tiếp bằng Microsoft PowerPoint và chưa chạy lại ví dụ thuật toán. Bước tiếp theo: người dùng mở bản nhiều chữ để duyệt phong cách và trình chiếu thử trên máy sử dụng.




