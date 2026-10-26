from __future__ import annotations

import base64
import csv
import hashlib
from contextlib import asynccontextmanager
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image
from skimage import exposure
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, FileResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .src.config import AppConfig, OFFICIAL_BUNDLE_NAME, feature_labels_for, default_weights_for, feature_specs_for
from .src.errors import AppError
from .src.features import extract_hog
from .src.rootsift import cluster_weights
from .src.spatial_features import spatial_weights
from .src.calibration_preparation import descriptor_bundle
from .src.models import CropBox, SearchRequest, SearchResponse, Weights
from .src.repository import Repository
from .src.search_service import SearchService
from .src.preprocessing import preprocess_image
from .src.processing_service import DatasetProcessingService, ProcessingJobs


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "frontend"
templates = Jinja2Templates(directory=FRONTEND_ROOT / "templates")


@lru_cache(maxsize=1)
def services() -> tuple[AppConfig, Repository, SearchService]:
    config = AppConfig.default(profile=OFFICIAL_BUNDLE_NAME)
    config.ensure_runtime_dirs()
    repository = Repository(config)
    repository.create_schema()
    return config, repository, SearchService(config, repository)


@lru_cache(maxsize=6)
def services_for_profile(profile: str):
    config = AppConfig.default(profile=profile)
    config.ensure_runtime_dirs()
    repository = Repository(config)
    repository.create_schema()
    return config, repository, SearchService(config, repository)


def request_services(request: Request):
    profile = request.query_params.get("profile")
    if profile is None:
        return services()
    if profile != OFFICIAL_BUNDLE_NAME:
        raise AppError("CONFIG_MISMATCH", f"Ứng dụng dùng cấu hình chính thức {OFFICIAL_BUNDLE_NAME} với 4 bộ mô tả")
    return services_for_profile(profile)


@lru_cache(maxsize=1)
def processing_jobs():
    return ProcessingJobs(DatasetProcessingService(AppConfig.default(profile=OFFICIAL_BUNDLE_NAME)))


def image_data_url(image: Image.Image | np.ndarray) -> str:
    if isinstance(image, np.ndarray):
        array = np.asarray(image)
        if np.issubdtype(array.dtype, np.floating):
            array = np.clip(array, 0.0, 1.0)
            array = np.rint(array * 255).astype(np.uint8)
        elif array.dtype != np.uint8:
            array = np.clip(array, 0, 255).astype(np.uint8)
        image = Image.fromarray(array)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def path_data_url(config: AppConfig, relative_path: str) -> str:
    with Image.open(config.resolve_data_path(relative_path)) as image:
        return image_data_url(image.convert("RGB"))


def result_image(config: AppConfig, original_path: str | None, processed_path: str) -> str:
    if not config.background_input and original_path is not None:
        try:
            if config.resolve_data_path(original_path).is_file():
                return path_data_url(config, original_path)
        except (OSError, ValueError, Image.DecompressionBombError):
            pass  # The validated processed image remains the display fallback.
    return path_data_url(config, processed_path)


def serialize_search(response: SearchResponse, config: AppConfig, repository: Repository) -> dict[str, Any]:
    weights = response.effective_weights
    bundle = repository.ensure_bundle()
    hog_vector, hog_image = extract_hog(response.processed_query.rgb, visualize=True, parameters=bundle.hog.parameters)
    del hog_vector
    hog_limit = float(np.percentile(hog_image, 99))
    hog_preview = exposure.rescale_intensity(
        hog_image,
        in_range=(0, hog_limit if hog_limit > 0 else 1.0),
    )
    vlad_clusters = None
    if "rootsift_vlad" in response.query_features.vectors:
        spec = bundle.configs["rootsift_vlad"]
        vlad_clusters = cluster_weights(response.query_features.vectors["rootsift_vlad"],
                                        int(spec.parameters["vlad"]["clusters"])).tolist()
    first_config = bundle.configs[next(iter(bundle.configs))]
    prior = first_config.parameters.get("spatial_prior")

    originals = repository.original_paths([item.image_id for item in response.items])
    items = []
    for item in response.items:
        contributions = item.scores.contributions(weights)
        items.append(
            {
                "rank": item.rank,
                "image_id": item.image_id,
                "species_name": item.species_name or "Chưa định danh",
                "image": result_image(config, originals.get(item.image_id), item.processed_path),
                "scores": {**item.scores.as_dict(), "total": item.scores.total},
                "contributions": contributions,
                "strongest": max(contributions, key=contributions.get).upper(),
            }
        )

    processing_ms = sum(
        response.timings.get(key, 0.0)
        for key in ("preprocess_ms", "extract_ms", "load_ms", "rank_ms")
    )
    return {
        "query_id": response.query_id,
        "items": items,
        "candidate_count": response.candidate_count,
        "weights": weights.as_dict(),
        "timings": {**response.timings, "processing_ms": processing_ms},
        "warnings": list(response.warnings),
        "feature_labels": {key: feature_labels_for(config.bundle_name)[key][0] for key in response.query_features.vectors},
        "query": {
            "rgb": image_data_url(response.processed_query.rgb),
            "hog": image_data_url(hog_preview),
            "spatial_hsv_bins": response.query_features.vectors["spatial_hsv"].reshape(4, 8, 4, 4).sum(axis=(0, 2, 3)).tolist(),
            "rootsift_vlad_clusters": vlad_clusters,
            "dimensions": {name: int(vector.size) for name, vector in response.query_features.vectors.items()},
            "extra_vectors": {name: vector.tolist() for name, vector in response.query_features.extras.items()},
            "spatial_prior": image_data_url(spatial_weights(response.processed_query.rgb.shape, prior)) if prior else None,
            "preview_notes": {
                "hog": ("HOG hai mức ô 32/64, có trọng số vùng" +
                        (f"; PCA còn {bundle.hog.dimension} chiều" if bundle.hog.parameters.get('pca') else "")) if prior else "HOG theo cấu hình tìm kiếm",
                "rootsift_vlad": "RootSIFT lưới đều ba mức, gộp VLAD 32 cụm" if prior else "VLAD theo cấu hình tìm kiếm",
            },
        },
    }


def dataset_manifest_stats(config: AppConfig) -> tuple[dict[str, int], dict[str, int]]:
    """Số ảnh theo split và theo loài (gallery) đọc từ manifest nguồn.

    Ảnh test không nhập CSDL nên không đếm được từ bảng images; phân bố gallery vẫn hiển thị được
    ngay cả khi chưa ảnh nào được duyệt mask.
    """
    splits: dict[str, int] = {}
    gallery_species: dict[str, int] = {}
    try:
        with config.source_manifest_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                splits[row["split"]] = splits.get(row["split"], 0) + 1
                if row["split"] == "gallery":
                    gallery_species[row["species_name"]] = gallery_species.get(row["species_name"], 0) + 1
    except OSError:
        return {}, {}
    return splits, gallery_species


def public_stats(repository: Repository, service: SearchService | None = None) -> dict[str, Any]:
    stats = repository.dashboard_stats()
    service = service or SearchService(repository.config, repository)
    try:
        loaded, _, _ = service.load_gallery()
    except AppError as exc:
        if exc.code not in {"CONFIG_MISMATCH", "CONFIG_CONFLICT"}:
            raise
        splits, gallery_species = dataset_manifest_stats(repository.config)
        return {**stats, "dataset_splits": splits, "dataset_gallery_by_species": gallery_species,
                "valid_candidates": 0, "rejected_candidates": [], "gallery_ready": False,
                "acceptance_ready": False, "calibration_ready": False, "setup_error": exc.message}
    splits, gallery_species = dataset_manifest_stats(repository.config)
    return {**stats, "dataset_splits": splits, "dataset_gallery_by_species": gallery_species,
            "valid_candidates": len(loaded.candidates),
            "rejected_candidates": [item.__dict__ for item in loaded.rejected],
            "gallery_ready": len(loaded.candidates) >= 5, "acceptance_ready": len(loaded.candidates) >= 500,
            "calibration_ready": True, "setup_error": None}


async def homepage(request: Request) -> HTMLResponse:
    config, repository, service = request_services(request)
    stats = await run_in_threadpool(public_stats, repository, service)
    weights = default_weights_for(config.bundle_name)
    if stats["calibration_ready"]:
        bundle = repository.ensure_bundle()
        weight_presets, preset_warning = await run_in_threadpool(service.weight_presets, bundle)
    else:
        bundle = descriptor_bundle(config, feature_specs_for(config.bundle_name))
        weight_presets = [{"label": "Trọng số khởi đầu", "weights": weights}]
        preset_warning = stats["setup_error"]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"stats": stats, "background_input": config.background_input,
         "automatic_background": True,
         "bundle_name": config.bundle_name, "image_size": config.image_size,
         "hog_dimension": bundle.hog.dimension,
         "total_dimensions": sum(spec.dimension for spec in bundle.configs.values()),
         "feature_info": [{"key": name, "label": feature_labels_for(config.bundle_name)[name][0], "description": feature_labels_for(config.bundle_name)[name][1],
                           "dimension": spec.dimension, "weight": weights[name]} for name, spec in bundle.configs.items()],
         "weight_presets": weight_presets, "preset_warning": preset_warning,
         "spatial_weighted": True,
         "asset_versions": {
             name: hashlib.sha256((FRONTEND_ROOT / "static" / name).read_bytes()).hexdigest()[:12]
             for name in ("app.css", "motion.css", "motion.js", "app.js")
         }},
        headers={"Cache-Control": "no-cache"},
    )


async def dashboard_api(request: Request) -> JSONResponse:
    _, repository, service = request_services(request)
    return JSONResponse(
        {
            "stats": await run_in_threadpool(public_stats, repository, service),
            "history": await run_in_threadpool(repository.recent_searches),
        }
    )


def optional_int(form: Any, key: str) -> int | None:
    value = form.get(key)
    if value is None or str(value).strip() == "":
        return None
    return int(value)


async def search_api(request: Request) -> JSONResponse:
    request_started = perf_counter()
    config, repository, search_service = request_services(request)
    try:
        form = await request.form()
        upload = form.get("image")
        if upload is None or not hasattr(upload, "read"):
            raise AppError("INVALID_IMAGE", "Vui lòng chọn một ảnh để tìm kiếm")
        image_bytes = await upload.read()
        if not image_bytes:
            raise AppError("INVALID_IMAGE", "Tệp ảnh đang trống")
        if len(image_bytes) > 20 * 1024 * 1024:
            raise AppError("INVALID_IMAGE", "Ảnh vượt quá giới hạn 20 MB")

        use_crop = str(form.get("use_crop", "false")).lower() == "true"
        crop = None
        if use_crop:
            x = optional_int(form, "crop_x")
            y = optional_int(form, "crop_y")
            size = optional_int(form, "crop_size")
            if x is None or y is None or size is None:
                raise AppError("INVALID_CROP", "Vùng cắt chưa có đủ tọa độ")
            crop = CropBox(x=x, y=y, size=size)

        segmentation_ms = 0.0
        defaults = default_weights_for(config.bundle_name)
        unknown_weights = set(form) - set(defaults) - {"image", "use_crop", "crop_x", "crop_y", "crop_size"}
        if any(name in form for name in unknown_weights):
            raise AppError("INVALID_WEIGHTS", "Trọng số không thuộc cấu hình đã chọn")
        response = await run_in_threadpool(
            search_service.search,
            SearchRequest(
                image_bytes=image_bytes,
                crop=crop,
                bundle_name=config.bundle_name,
                weights=Weights.from_dict({name: float(form.get(name, value)) for name, value in defaults.items()}),
            ),
        )
        preview_started = perf_counter()
        result = await run_in_threadpool(serialize_search, response, config, repository)
        result["timings"].update(segmentation_ms=response.timings.get("segmentation_ms", segmentation_ms),
                                 preview_ms=(perf_counter() - preview_started) * 1000,
                                 request_ms=(perf_counter() - request_started) * 1000)
        return JSONResponse(result)
    except AppError as exc:
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status_code=422,
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse(
            {"error": {"code": "INVALID_REQUEST", "message": "Tham số tìm kiếm không hợp lệ", "details": {"reason": str(exc)}}},
            status_code=422,
        )


async def history_api(request: Request) -> JSONResponse:
    config, repository, _ = request_services(request)
    query_id = int(request.path_params["query_id"])
    rows = repository.get_search_items(query_id)
    originals = repository.original_paths([row["image_id"] for row in rows])
    items = []
    for row in rows:
        items.append(
            {
                **row,
                "species_name": row.get("species_name") or "Chưa định danh",
                "image": result_image(config, originals.get(row["image_id"]), row["processed_path"]),
            }
        )
    if not items:
        return JSONResponse(
            {"error": {"code": "NOT_FOUND", "message": "Không tìm thấy truy vấn này"}},
            status_code=404,
        )
    return JSONResponse({"query_id": query_id, "items": items})


async def processing_api(request: Request) -> JSONResponse:
    request_services(request)
    jobs = processing_jobs()
    if request.method == "GET":
        catalog = await run_in_threadpool(jobs.service.catalog,
                                         int(request.query_params.get("offset", 0)),
                                         int(request.query_params.get("limit", 24)),
                                         request.query_params.get("ready_only", "false") == "true")
        return JSONResponse({**catalog, "job": jobs.latest(), "busy": jobs.busy})
    body = await request.json()
    if not isinstance(body, dict):
        raise ValueError("Invalid processing request")
    job = jobs.start(body.get("action"), body.get("limit"))
    return JSONResponse(job, status_code=202)


async def processing_cancel_api(request: Request) -> JSONResponse:
    request_services(request)
    return JSONResponse({"job": processing_jobs().cancel()})


async def processing_review_api(request: Request) -> JSONResponse:
    request_services(request)
    jobs = processing_jobs()
    if jobs.busy:
        raise AppError("PROCESSING_BUSY", "Hãy đợi tác vụ hoàn tất trước khi duyệt ảnh")
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("source_ids"), list):
        raise ValueError("Choose source images to review")
    result = await run_in_threadpool(jobs.service.review, body["source_ids"], body.get("quality_status"))
    return JSONResponse(result)


async def processing_preview_api(request: Request):
    request_services(request)
    path = await run_in_threadpool(processing_jobs().service.preview_path,
                                  request.path_params["source_id"], request.path_params["kind"])
    return FileResponse(path, media_type="image/png")


async def app_error(request, exc):
    return JSONResponse({"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
                        status_code=409 if exc.code == "PROCESSING_BUSY" else 422)


async def request_error(request, exc):
    return JSONResponse({"error": {"code": "INVALID_REQUEST", "message": str(exc)}}, status_code=422)


async def missing_file(request, exc):
    return JSONResponse({"error": {"code": "NOT_FOUND", "message": str(exc)}}, status_code=404)


@asynccontextmanager
async def lifespan(app):
    yield
    if hasattr(processing_jobs, "cache_info") and processing_jobs.cache_info().currsize:
        await run_in_threadpool(processing_jobs().shutdown)


routes = [
    Route("/", homepage),
    Route("/api/dashboard", dashboard_api),
    Route("/api/search", search_api, methods=["POST"]),
    Route("/api/history/{query_id:int}", history_api),
    Route("/api/processing", processing_api, methods=["GET", "POST"]),
    Route("/api/processing/cancel", processing_cancel_api, methods=["POST"]),
    Route("/api/processing/review", processing_review_api, methods=["POST"]),
    Route("/api/processing/preview/{source_id:int}/{kind}", processing_preview_api),
]

app = Starlette(debug=False, routes=routes, lifespan=lifespan,
                exception_handlers={AppError: app_error, ValueError: request_error, FileNotFoundError: missing_file})
app.mount("/static", StaticFiles(directory=FRONTEND_ROOT / "static"), name="static")
