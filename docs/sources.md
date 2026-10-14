# Nguồn dữ liệu và tài liệu tham khảo

## Nguồn đang dùng — AFHQ v2, ngày 10/10/2026

600 ảnh hiện hành đều từ Animal Faces-HQ v2 của NAVER/Clova AI, gồm cat, dog và các nhãn được duyệt trong wild. Phân bố tại [dataset.md](dataset.md).

- Trang chính thức: https://github.com/clovaai/stargan-v2#animal-faces-hq-dataset-afhq
- Archive chính thức: https://dl.dropboxusercontent.com/s/vkzjokiwof5h8w6/afhq_v2.zip
- Giấy phép: CC BY-NC 4.0, dùng phi thương mại và ghi công NAVER Corporation.
- Bài báo: [StarGAN v2, Choi et al., CVPR 2020](https://arxiv.org/abs/1912.01865).
- Thông báo giấy phép giữ tại `data/manifests/afhq-v2-NOTICE.txt`.
- Archive đã tải trước được tái sử dụng và xác minh: 6.955.288.636 byte; SHA-256 `6f2540f22c6d8ebb8879a2bc0227666dd4fc765cc355cb073b63a835d679e4e3`; MD5 `63552c42da100f769ab26356202049d2`.

AFHQ v2 phát hành PNG 512×512; bản v2 dùng Lanczos thay cho phép resize của bản cũ. Ảnh nguồn được chọn giữ nguyên byte phát hành, không tự tăng kích thước/crop/tô màu. Native512 tính trực tiếp trên RGB 512×512; không resize xuống 128. Profile tách nền giữ RGB nguồn và thêm alpha, chụp snapshot mask rồi ghép nền trắng 512 để tính; metadata kế thừa nguồn/giấy phép và ghi rõ biến đổi.

[Nguồn từng ảnh](../data/manifests/frontal512_sources.csv) có đúng 600 dòng: đường dẫn runtime, nhóm nhãn, trang nguồn, URL archive, tên thành viên trong ZIP, SHA-256, giấy phép, ghi công, thay đổi và mã duyệt. Manifest nhập cũng giữ source_archive/source_member.

Archive không cung cấp URL trang gốc hoặc tên tác giả từng ảnh Flickr/Pixabay. Tên file chứa flickr/pixabay chỉ là tên do bộ dữ liệu phát hành; không tự dựng URL hoặc gán tác giả cá nhân từ tên này. Đây là truy vết đầy đủ đến file trong dataset, chưa phải attribution đến từng nhiếp ảnh gia.

## Các nguồn lịch sử

Phần bên dưới ghi lại snapshot cũ và các bộ đề xuất/tải bổ sung. Các đường dẫn cũ là vị trí tại thời điểm thực hiện; dữ liệu đó đã rời runtime. Bản phục hồi hiện giữ trong project là `data/backups/before-native512-20261010.zip` (600 ảnh và pipeline 128 trước chuyển 512). ZIP mixed-20 cũ đã chuyển vào `../BTL_luu_tru_20261010/obsolete-after-native512/`. Ảnh cũ dư ở obsolete-after-frontal512, nguồn chưa dùng ở unused/data; việc xóa hẳn chưa thực hiện do lệnh bị kiểm duyệt tự động chặn.

## Tài liệu đầu vào của bài tập

| Tài liệu | File trong project | Mục đích |
| --- | --- | --- |
| Đề bài gốc | `docs/references/assignment-requirements.docx` | Yêu cầu ít nhất 500 ảnh, lưu đặc trưng trong CSDL và trả top 5 |


## AFHQ — nguồn cat và dog

- Tên: Animal Faces-HQ (AFHQ), phát hành cùng StarGAN v2 bởi NAVER/Clova AI Research.
- Repository chính thức: <https://github.com/clovaai/stargan-v2>
- Mô tả AFHQ: <https://github.com/clovaai/stargan-v2#animal-faces-hq-dataset-afhq>
- Bài báo: <https://arxiv.org/abs/1912.01865>
- Giấy phép: Creative Commons Attribution-NonCommercial 4.0.
- Văn bản giấy phép: <https://github.com/clovaai/stargan-v2/blob/master/LICENSE>
- Kênh truyền tải dùng trong project: <https://huggingface.co/datasets/huggan/AFHQ>

Hai shard mirror:

- <https://huggingface.co/datasets/huggan/AFHQ/resolve/main/data/train-00000-of-00002.parquet>
- <https://huggingface.co/datasets/huggan/AFHQ/resolve/main/data/train-00001-of-00002.parquet>

Mirror chỉ là kênh tải ổn định; nguồn tác giả và giấy phép vẫn theo repository StarGAN v2. Snapshot mixed-20 cũ chỉ dùng hai miền `cat` và `dog` của AFHQ.

## AFD — nguồn 18 loại còn lại

- Tên: AFD (Animal Face Dataset).
- Tác giả công bố: Pengfei Xu, Northwest University.
- Trang dữ liệu chính thức: <https://data.mendeley.com/datasets/z3x59pv4bz/7>
- DOI: <https://doi.org/10.17632/z3x59pv4bz.2>
- Bài báo mô tả: <https://pmc.ncbi.nlm.nih.gov/articles/PMC7415925/>
- Giấy phép trên Mendeley Data: Creative Commons Attribution 4.0.

Snapshot dùng 18 archive AFD, tổng khoảng 470,2 MiB nén:

1. Ailurus fulgens
2. Cebus apella
3. Cebus olivaceus
4. Cercopithecus neglectus
5. Cercopithecus nictitans
6. Chlorocebus sabaeus
7. Erythrocebus patas
8. Lemur catta
9. Macaca fascicularis
10. Macaca thibetana
11. Mandrillus sphinx
12. mongooses
13. Nomascus leucogenys
14. Pan troglodytes
15. Panthera leo
16. Panthera tigris
17. Papio anubis
18. Saimiri sciureus

`scripts/download_afd.py` chứa URL và SHA-256 chính thức cho từng archive. `scripts/prepare_mixed_animals.py` đọc trực tiếp archive, áp dụng rejection audit và tạo snapshot cân bằng.

## Snapshot kết hợp cũ (đã rời runtime)

| Split | Cat | Dog | 18 loại AFD | Tổng |
| --- | ---: | ---: | ---: | ---: |
| Gallery | 25 | 25 | 450 | 500 |
| Validation | 5 | 5 | 90 | 100 |
| Test | 5 | 5 | 90 | 100 |

- Manifest: `data/manifests/mixed_20_manifest.csv`.
- Trạng thái: 700/700 dòng `approved`.
- Rejection audit: `data/manifests/mixed_20_rejections.csv` với 1.258 source member.
- Contact sheet cũ sau dọn: `../BTL_luu_tru_20261010/unused/data/review/mixed-20/` tính từ gốc BTL.
- Báo cáo gần trùng: `data/statistics/mixed_20_near_duplicates.csv`.
- Database tại thời điểm cũ: `data/app.db`.
- Backup AFHQ ba miền cũ: `data/backups/2026-09-28-afhq-three-domain/`.

Mẫu ghi công ngắn:

> Project sử dụng cat/dog từ Animal Faces-HQ của NAVER (CC BY-NC 4.0) và 18 loại động vật từ Animal Face Dataset của Pengfei Xu trên Mendeley Data (CC BY 4.0). Mọi ảnh trong snapshot được truy vết qua manifest và đã qua sàng lọc trực quan.

## Nguồn ảnh đề xuất thay thế ngày 2026-10-10

Bộ đề xuất riêng tại `data/replacements/20261010/` gồm 7 ảnh AFHQ/AFD chưa dùng trong manifest hiện hành và 5 ảnh Wikimedia Commons. Chưa tích hợp các ảnh này vào `data/app.db`; phần mô tả snapshot đang hoạt động ở trên tiếp tục áp dụng cho dữ liệu cũ.

Metadata chi tiết, tác giả, giấy phép, URL tải và biến thể original/thumbnail của các ảnh Commons được lưu tại `data/replacements/20261010/source-attribution.json`; bảng ánh xạ 12 ảnh cũ–mới nằm tại `replacement-map.csv` cùng thư mục. Trang nguồn được xác minh qua Commons API imageinfo/extmetadata:

- Cebus olivaceus: <https://commons.wikimedia.org/wiki/File:Cebus_olivaceus_345587067.jpg>.
- Meerkat: <https://commons.wikimedia.org/wiki/File:Face_of_meerkat.jpg>.
- Meerkat chính diện: <https://commons.wikimedia.org/wiki/File:Look_into_my_eyes,_you_are_feeling_verrrry_sleeeeepy......._(5551612028).jpg>.
- Hổ: <https://commons.wikimedia.org/wiki/File:Bengal_Tiger_Portrait.jpg>.
- Saimiri sciureus: <https://commons.wikimedia.org/wiki/File:Saimiri_sciureus_254640208.jpg>.

Ảnh được crop và resize bằng pipeline hiện hành; ghi nhận các biến đổi này khi ghi công. Không coi giấy phép Commons chung là giấy phép của mọi file; dùng giấy phép cụ thể trong attribution.

## Bộ nguồn mặt động vật tải bổ sung ngày 2026-10-10

Theo yêu cầu tải bộ nguồn miễn phí để chọn ảnh chất lượng hơn, đã chọn AFHQ v2 (NAVER, CC BY-NC 4.0), CatFLW v2 (Tech4Animals/University of Haifa, CC BY-NC 4.0) và bộ tuyển chính diện chất lượng cao từ Mandrillus Face Database (CC BY 4.0). AFHQ v2 hiện được chọn cho snapshot mới; CatFLW và Mandrillus chưa nhập runtime.

- AFHQ v2: <https://github.com/clovaai/stargan-v2#animal-faces-hq-dataset-afhq>.
- CatFLW: <https://github.com/martvelge/CatFLW>; bản phát hành tác giả trên <https://www.kaggle.com/datasets/georgemartvel/catflw>.
- Mandrillus: <https://doi.org/10.5281/zenodo.7467318>; tác giả Sonia Tieo, Julien P. Renoult, Marie Charpentier, Claudia Restrepo-Ortiz, Berta Roura-Torres, Loic Sauvadet và Mélanie Harté. Bộ tuyển giữ byte ảnh gốc, chọn theo FaceQual=3/FaceView=1 và màu; không phải toàn bộ archive nguồn.

Thông tin so sánh, giới hạn và cách tải ở [bản lưu trữ hq-face-datasets-20261010.md](../../BTL_luu_tru_20261010/docs/hq-face-datasets-20261010.md). Metadata/giấy phép/checksum và catalog đã chuyển vào `../BTL_luu_tru_20261010/unused/data/downloads/hq-faces-20261010/` và `../BTL_luu_tru_20261010/unused/data/review/hq-faces-20261010/` tính từ gốc BTL. AFHQ v2 có thể trùng cảnh với AFHQ cũ; thay phiên bản file không tạo query độc lập.

## Nguồn thuật toán

### HSV

- NumPy histogramdd: <https://numpy.org/doc/stable/reference/generated/numpy.histogramdd.html>
- scikit-image RGB/HSV: <https://scikit-image.org/docs/stable/api/skimage.color.html#skimage.color.rgb2hsv>
- Cấu hình project: histogram 8×4×4, 128 chiều, chuẩn hóa L1.

### HOG

- Dalal, N. và Triggs, B., “Histograms of Oriented Gradients for Human Detection”, CVPR 2005.
- DOI: <https://doi.org/10.1109/CVPR.2005.177>
- API: <https://scikit-image.org/docs/stable/api/skimage.feature.html#skimage.feature.hog>
- Cấu hình project: 9 hướng, cell 16×16, block 2×2, L2-Hys, 1.764 chiều.

### LBP

- Ojala, T., Pietikäinen, M. và Mäenpää, T., “Multiresolution Gray-Scale and Rotation Invariant Texture Classification with Local Binary Patterns”, IEEE TPAMI 2002.
- DOI: <https://doi.org/10.1109/TPAMI.2002.1017623>
- API: <https://scikit-image.org/docs/stable/api/skimage.feature.html#skimage.feature.local_binary_pattern>
- Cấu hình project: uniform LBP P=8, R=1 trên lưới 4×4, 160 chiều.

## Công nghệ triển khai

| Thành phần | Nguồn chính thức | Vai trò |
| --- | --- | --- |
| SQLite | <https://www.sqlite.org/docs.html> | Metadata, vector và lịch sử truy vấn |
| Python sqlite3 | <https://docs.python.org/3/library/sqlite3.html> | Kết nối, SQL và transaction |
| Starlette | <https://www.starlette.io/> | Máy chủ web và endpoint cục bộ của giao diện |
| scikit-image | <https://scikit-image.org/docs/stable/> | Màu, HOG, LBP |
| NumPy | <https://numpy.org/doc/stable/> | Vector và similarity |
| Pillow | <https://pillow.readthedocs.io/> | Đọc, crop và resize ảnh |
| DB Browser for SQLite | <https://sqlitebrowser.org/dl/> | Công cụ ngoài project để xem `data/app.db` |

Phiên bản thực tế được khóa trong `requirements.lock`.

## Cam kết phạm vi

- Không dùng ảnh sinh bởi AI trong gallery, validation hoặc test.
- Không dùng tên file hoặc nhãn loài để lọc candidate trước khi xếp hạng.
- Điểm P@5, latency và top 5 được tạo từ code và snapshot cục bộ của project.
- Manifest là bằng chứng nguồn ở cấp từng ảnh; các URL trên là nguồn cấp dataset/tài liệu.
