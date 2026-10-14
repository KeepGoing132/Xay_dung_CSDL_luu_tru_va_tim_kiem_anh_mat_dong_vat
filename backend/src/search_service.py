from __future__ import annotations

from hashlib import sha256
import json
from time import perf_counter
from uuid import uuid4

from .config import AppConfig, default_weights_for, FEATURE_LABELS
from .features import extract_features
from .models import SearchRequest, SearchResponse, Weights
from .preprocessing import encode_processed_png, preprocess_image
from .repository import Repository
from .similarity import normalize_weights, rank_candidates
from .errors import AppError, invalid


class SearchService:
    def __init__(self, config: AppConfig, repository: Repository):
        self.config = config
        self.repository = repository
        self._candidate_cache = None

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return (perf_counter() - start) * 1000.0

    def load_gallery(self, bundle=None):
        bundle = bundle or self.repository.ensure_baseline_bundle()
        fingerprint = self.repository.gallery_fingerprint(bundle)
        cached = self._candidate_cache
        if cached is not None and cached[0] == fingerprint:
            return cached[1], fingerprint, True
        loaded = self.repository.load_candidates(bundle)
        self._candidate_cache = (fingerprint, loaded)
        return loaded, fingerprint, False

    def weight_presets(self, bundle):
        keys = list(bundle.configs)
        presets = [
            {"label": "Trọng số khởi đầu", "weights": default_weights_for(bundle.name)},
            {"label": "Các nhóm bằng nhau", "weights": {key: 1 / len(keys) for key in keys}},
            *({"label": f"Chỉ {FEATURE_LABELS[key][0]}", "weights": {name: float(name == key) for name in keys}} for key in keys),
        ]
        path = self.config.result_directory("evaluation") / "selected_weights.json"
        if not path.exists():
            return presets, None
        try:
            selected = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(selected, dict) or not isinstance(selected.get("weights"), dict):
                raise ValueError("Selected weights must be a JSON object")
            fingerprint = self.repository.gallery_fingerprint(bundle)
            signature = {"bundle_name": bundle.name, "config_ids": bundle.config_ids,
                         "manifest_sha256": sha256(self.config.default_manifest_path.read_bytes()).hexdigest(),
                         "gallery_fingerprint_sha256": sha256(repr(fingerprint).encode()).hexdigest()}
            if selected.get("signature") != signature:
                return presets, "Trọng số validation đã cũ; cần đánh giá lại trên dữ liệu hiện tại."
            weights = normalize_weights(Weights.from_dict(selected["weights"]))
            if set(weights.as_dict()) - set(keys):
                raise ValueError("Unknown feature in selected weights")
            presets.append({"label": "Theo validation · độ trùng nhãn", "weights": {key: weights.as_dict().get(key, 0) for key in keys}})
            return presets, None
        except (OSError, ValueError, KeyError, TypeError, AppError) as exc:
            return presets, f"Không đọc được bộ trọng số validation: {exc}"

    def search(self, request: SearchRequest) -> SearchResponse:
        if request.bundle_name != self.config.bundle_name:
            raise invalid("CONFIG_MISMATCH", "Bundle không được hỗ trợ", bundle_name=request.bundle_name)
        timings: dict[str, float] = {}
        start = perf_counter()
        effective_weights = normalize_weights(request.weights)
        processed = preprocess_image(
            request.image_bytes, request.crop, preprocess_version=self.config.preprocess_version
        )
        timings["preprocess_ms"] = self._elapsed_ms(start)

        bundle = self.repository.ensure_baseline_bundle()
        start = perf_counter()
        query_features = extract_features(processed, bundle)
        timings["extract_ms"] = self._elapsed_ms(start)

        start = perf_counter()
        loaded, fingerprint, cache_hit = self.load_gallery(bundle)
        timings["load_ms"] = self._elapsed_ms(start)
        if len(loaded.candidates) < 5:
            raise invalid("INSUFFICIENT_GALLERY", "Gallery không đủ 5 ảnh hợp lệ",
                          candidate_count=len(loaded.candidates), required=5,
                          rejected=[item.__dict__ for item in loaded.rejected])

        start = perf_counter()
        items = rank_candidates(query_features, loaded.candidates, effective_weights, k=5)
        timings["rank_ms"] = self._elapsed_ms(start)

        query_path = self.config.result_directory("queries") / f"query-{uuid4().hex}.png"
        query_path.parent.mkdir(parents=True, exist_ok=True)
        query_path.write_bytes(encode_processed_png(processed))
        query_relative = self.config.relative_to_data(query_path)
        warnings = list(query_features.warnings)
        if cache_hit:
            warnings.append("candidate_cache_hit")
        if loaded.rejected:
            warnings.append(f"Đã loại {len(loaded.rejected)} ảnh gallery lỗi hoặc thiếu dữ liệu")
            warnings.extend(f"Ảnh #{item.image_id} · {item.processed_path}: {item.reason}" for item in loaded.rejected)

        start = perf_counter()
        try:
            query_id = self.repository.save_search(
                query_path=query_relative,
                query_sha256=processed.pixel_sha256,
                bundle=bundle,
                weights=effective_weights,
                candidate_count=len(loaded.candidates),
                timings=timings,
                items=items,
                gallery_signature=sha256(repr(fingerprint).encode("utf-8")).hexdigest(),
            )
        except Exception:
            query_path.unlink(missing_ok=True)
            raise
        timings["persist_ms"] = self._elapsed_ms(start)
        return SearchResponse(
            query_id=query_id,
            query_path=query_relative,
            items=items,
            effective_weights=effective_weights,
            candidate_count=len(loaded.candidates),
            timings=timings,
            warnings=tuple(warnings),
            query_features=query_features,
            processed_query=processed,
        )
