from __future__ import annotations

from hashlib import sha256
from io import BytesIO

import numpy as np
from PIL import Image
import pytest

from backend.src.errors import AppError
from backend.src.features import extract_features
from backend.src.models import ImageMetadata, SearchRequest, Weights
from backend.src.preprocessing import encode_processed_png, preprocess_image
from backend.src.repository import Repository
from backend.src.search_service import SearchService


def make_png(color: tuple[int, int, int], stripe: bool = False) -> bytes:
    array = np.full((160, 160, 3), color, dtype=np.uint8)
    if stripe:
        array[:, 70:90] = 255 - array[:, 70:90]
    stream = BytesIO()
    Image.fromarray(array, mode="RGB").save(stream, format="PNG")
    return stream.getvalue()


def insert_gallery(repository: Repository, app_config, count: int = 5) -> list[int]:
    bundle = repository.ensure_baseline_bundle()
    ids = []
    for index in range(count):
        payload = make_png((30 + index * 20, 80, 140), stripe=index % 2 == 0)
        processed = preprocess_image(payload)
        relative = f"processed/gallery/cat/{index}.png"
        destination = app_config.resolve_data_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encode_processed_png(processed))
        metadata = ImageMetadata(
            species_name="cat",
            original_path=f"original/gallery/cat/{index}.png",
            processed_path=relative,
            original_sha256=sha256(payload).hexdigest(),
            processed_sha256=processed.pixel_sha256,
            source_url=None,
            license_note=None,
            split="gallery",
            group_id=f"g-{index}",
            crop=processed.crop,
            preprocess_version=processed.preprocess_version,
            quality_status="approved",
            active=True,
        )
        ids.append(repository.insert_image_with_features(metadata, extract_features(processed, bundle), bundle))
    return ids


def test_search_persists_exactly_five_results(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    insert_gallery(repository, app_config, 6)
    response = SearchService(app_config, repository).search(
        SearchRequest(make_png((40, 80, 140), stripe=True), weights=Weights(2, 1, 1))
    )
    assert len(response.items) == 5
    assert len({item.image_id for item in response.items}) == 5
    assert [item.rank for item in response.items] == [1, 2, 3, 4, 5]
    assert all(response.items[i].scores.total >= response.items[i + 1].scores.total for i in range(4))
    assert repository.get_search_items(response.query_id)[0]["rank"] == 1


def test_candidate_cache_is_reused_without_changing_results(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    insert_gallery(repository, app_config, 5)
    service = SearchService(app_config, repository)
    request = SearchRequest(make_png((40, 80, 140), stripe=True))
    first = service.search(request)
    second = service.search(request)
    assert "candidate_cache_hit" not in first.warnings
    assert "candidate_cache_hit" in second.warnings
    assert [item.image_id for item in first.items] == [item.image_id for item in second.items]


def test_duplicate_checksum_is_rejected(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    insert_gallery(repository, app_config, 1)
    bundle = repository.ensure_baseline_bundle()
    payload = make_png((30, 80, 140), stripe=True)
    processed = preprocess_image(payload)
    metadata = ImageMetadata(
        species_name="cat", original_path="another.png", processed_path="processed/gallery/cat/another.png",
        original_sha256=sha256(payload).hexdigest(), processed_sha256=processed.pixel_sha256,
        source_url=None, license_note=None, split="gallery", group_id="duplicate",
        crop=processed.crop, preprocess_version=processed.preprocess_version,
        quality_status="approved", active=True,
    )
    with pytest.raises(AppError) as caught:
        repository.insert_image_with_features(metadata, extract_features(processed, bundle), bundle)
    assert caught.value.code == "DUPLICATE_IMAGE"


def test_insufficient_gallery(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    insert_gallery(repository, app_config, 4)
    with pytest.raises(AppError) as caught:
        SearchService(app_config, repository).search(SearchRequest(make_png((20, 20, 20))))
    assert caught.value.code == "INSUFFICIENT_GALLERY"


def test_cache_invalidates_after_in_place_vector_edit(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    ids = insert_gallery(repository, app_config, 6)
    service = SearchService(app_config, repository)
    request = SearchRequest(make_png((40, 80, 140), stripe=True))
    service.search(request)
    # Same row count and IDs; the old count-based fingerprint missed this.
    with repository.connect() as connection:
        connection.execute("UPDATE image_features SET vector_json='[]' WHERE image_id=? AND config_id=1", (ids[0],))
        connection.commit()
    result = service.search(request)
    assert result.candidate_count == 5
    assert ids[0] not in {item.image_id for item in result.items}
    assert "candidate_cache_hit" not in result.warnings


def test_cache_recovers_restored_file(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    insert_gallery(repository, app_config, 6)
    image = app_config.resolve_data_path("processed/gallery/cat/0.png")
    payload = image.read_bytes()
    image.unlink()
    service = SearchService(app_config, repository)
    request = SearchRequest(make_png((40, 80, 140), stripe=True))
    assert service.search(request).candidate_count == 5
    image.write_bytes(payload)
    result = service.search(request)
    assert result.candidate_count == 6
    assert "candidate_cache_hit" not in result.warnings


def test_bad_gallery_path_is_rejected_without_aborting_search(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    ids = insert_gallery(repository, app_config, 6)
    with repository.connect() as connection:
        connection.execute("UPDATE images SET processed_path='../outside.png' WHERE image_id=?", (ids[0],))
        connection.commit()
    loaded = repository.load_candidates(repository.ensure_baseline_bundle())
    assert len(loaded.candidates) == 5
    assert loaded.rejected[0].reason == "INVALID_IMAGE_PATH"


def test_revision_migration_is_idempotent_and_rolls_back(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    insert_gallery(repository, app_config, 5)
    bundle = repository.ensure_baseline_bundle()
    before = repository.gallery_fingerprint(bundle)
    repository.create_schema()
    with repository.connect() as connection:
        assert [r[0] for r in connection.execute("SELECT version FROM schema_migrations ORDER BY version")] == [1, 2, 3, 4]
        connection.execute("UPDATE images SET active=0")
        connection.rollback()
    assert repository.gallery_fingerprint(bundle) == before
