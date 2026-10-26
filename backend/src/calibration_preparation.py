"""Prepare immutable gallery-only calibration and the frozen VLAD codebook."""
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from importlib.metadata import version
import json
from .calibration import calibration_path, fit_calibration, canonical_hash, calibrated_specs
from .codebook import fit_codebook_artifact, with_codebook_specs
from .config import feature_specs_for
from .features import extract_features
from .ingestion import IngestionService
from .models import BundleConfig, FeatureConfig
from .preprocessing import preprocess_image
from .pca import attach_projection, with_pca_specs

def descriptor_bundle(config, specs):
    groups = {name: FeatureConfig(i, spec["name"], spec["feature_type"], spec["dimension"],
                                 spec["parameters"], config.preprocess_version)
              for i, (name, spec) in enumerate(specs.items(), 1)}
    return attach_projection(config, BundleConfig.from_configs(config.bundle_name, groups))


def _calibration_row(job):
    config, specs, row = job
    try:
        image = preprocess_image(config.resolve_data_path(row["relative_path"]).read_bytes(),
                                 IngestionService._crop_from_row(row), preprocess_version=config.preprocess_version)
        computed = extract_features(image, descriptor_bundle(config, specs)).vectors
        return image.pixel_sha256, computed
    except Exception as exc:
        raise ValueError(f"Calibration failed: {row['relative_path']}: {exc}") from exc


def _gallery_image(job):
    config, row = job
    payload = config.resolve_data_path(row["relative_path"]).read_bytes()
    image = preprocess_image(payload, IngestionService._crop_from_row(row),
                             preprocess_version=config.preprocess_version)
    return row["relative_path"], image.rgb


def prepare_codebook(config, specs, gallery, workers=1):
    """Fit codebook VLAD trên ảnh gallery đã tiền xử lý; tái dùng artifact đóng băng nếu còn khớp."""
    if not any("vlad" in spec["parameters"] for spec in specs.values()):
        return None
    jobs = [(config, row) for row in gallery]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            images = list(executor.map(_gallery_image, jobs))
    else:
        images = [_gallery_image(job) for job in jobs]
    return fit_codebook_artifact(config, specs, images)


def prepare_calibration(config, rows, minimum_gallery=500, workers=1):
    specs = feature_specs_for(config.bundle_name, config.preprocess_version)
    path = calibration_path(config)
    groups, paths = {}, set()
    for row in rows:
        if row["relative_path"] in paths:
            raise ValueError(f"Duplicate path: {row['relative_path']}")
        paths.add(row["relative_path"])
        groups.setdefault(row["group_id"], set()).add(row["split"])
    if any(len(splits) > 1 for splits in groups.values()):
        raise ValueError("Source group crosses dataset splits")
    gallery = sorted((row for row in rows if row["split"] == "gallery" and row["quality_status"] == "approved"),
                     key=lambda row: row["relative_path"])
    if len(gallery) < minimum_gallery:
        raise ValueError(f"Need {minimum_gallery} approved gallery images, got {len(gallery)}")
    # Codebook VLAD phải đóng băng trước khi trích vector, nên fit ngay tại đây, gallery-only.
    prepare_codebook(config, specs, gallery, workers=workers)
    specs = with_codebook_specs(config, specs)
    specs = with_pca_specs(config, specs)
    source_records = []
    digest_records = []
    for row in gallery:
        payload = config.resolve_data_path(row["relative_path"]).read_bytes()
        digest = sha256(payload).hexdigest()
        crop = [row.get(key, "") for key in ["crop_x", "crop_y", "crop_size"]]
        source_records.append({"path": row["relative_path"], "sha256": digest, "crop": crop})
        digest_records.append({"sha256": digest, "crop": crop})
    # Hash theo nội dung + crop, sắp xếp lại nên đổi tên/đường dẫn file mask không tính là đổi gallery.
    source_hash = canonical_hash(sorted(digest_records, key=lambda record: (record["sha256"], repr(record["crop"]))))
    if path.exists():
        calibrated_specs(config, specs)
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("gallery_source_sha256") != source_hash:
            raise ValueError("Gallery changed after calibration; create a new profile instead of overwriting")
        print("Reusing frozen calibration", flush=True)
        return artifact
    vectors = {key: [] for key in specs}
    seen_pixels = set()
    jobs = [(config, specs, row) for row in gallery]
    def collect(results):
        for index, (pixel_hash, computed) in enumerate(results, 1):
            if pixel_hash in seen_pixels:
                raise ValueError(f"Duplicate gallery pixels: {gallery[index-1]['relative_path']}")
            seen_pixels.add(pixel_hash)
            for key, vector in computed.items():
                vectors[key].append(vector)
            if index % 25 == 0:
                print(f"Calibration descriptors {index}/{len(gallery)}", flush=True)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            collect(executor.map(_calibration_row, jobs))
    else:
        collect(map(_calibration_row, jobs))
    artifact = fit_calibration(vectors, specs, profile=config.bundle_name)
    artifact.update(gallery_source_sha256=source_hash, source_records=source_records,
                    preprocessing_version=config.preprocess_version,
                    libraries={key: version(key) for key in ["numpy", "scipy", "scikit-image", "pillow"]},
                    note="Gallery only; no species labels, validation or test images used. Not a relevance probability.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(artifact, stream, indent=2)
    return artifact

