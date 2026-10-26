"""Tách bộ ảnh nguồn thành tập gallery (nhập CSDL) và tập test (query), 5 ảnh mỗi loài.

Quy tắc (cố định, tái lập được bằng cùng một seed):

- Mỗi ảnh chỉ thuộc một tập: `gallery` (nhập CSDL để truy hồi) hoặc `test` (query
  đánh giá, không vào CSDL tìm kiếm). Không còn dòng `unassigned`.
- Mỗi loài có đúng `--test-per-species` ảnh test, mặc định 5 và bắt buộc trong
  khoảng 4-5.
- Ảnh test phải có `quality_status=approved` và `group_id` không dùng chung với ảnh
  khác (nhóm nhiều ảnh giữ trọn trong gallery để nhóm không xuyên split).
- Chọn tất định, không dùng ngẫu nhiên có trạng thái: xếp hạng theo
  sha256(seed|loài|relative_path) và lấy 5 digest nhỏ nhất, nên chạy lại cho cùng kết quả.
  Mỗi loài lấy luân phiên giữa các đợt tuyển (selection_source) để tập test không dồn
  vào một đợt nguồn duy nhất.
- `--approve-reviewed-candidates` chuyển `reviewed_candidate` thành `approved` kèm ghi
  chú, vì CSDL/chấm điểm chỉ nhận pending/approved/rejected; cần thiết để tập gallery
  nhập được vào CSDL.

`check` kiểm tra lại các bất biến trên manifest và đối chiếu cột split với manifest chạy
manifest nguồn của profile đang chọn. Profile PCA512 mặc định ánh xạ test gốc thành validation.

`export` sao 50 ảnh test ra một thư mục riêng (mặc định data/dataset512-test) kèm
manifest-test.csv, README.md và kiểm checksum; ảnh gốc trong dataset512-left giữ nguyên.
"""
from pathlib import Path
import argparse
import csv
from collections import Counter
from hashlib import sha256
import json
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig

PROMOTION_NOTE = "AI visual review passed; promoted to approved for the gallery/test split 20/10/2026"
MIN_TEST_PER_SPECIES = 4
MAX_TEST_PER_SPECIES = 5


def load(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def write(path: Path, fields: list[str], rows: list[dict]) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def rank(seed: str, row: dict) -> str:
    return sha256(f"{seed}|{row['species_name']}|{row['relative_path']}".encode("utf-8")).hexdigest()


def singleton_groups(rows: list[dict]) -> set[str]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["group_id"]] = counts.get(row["group_id"], 0) + 1
    return {group for group, count in counts.items() if count == 1}


def assign(rows, *, seed, per_species, approve_reviewed, present:
           set[str] | None = None):
    promoted = []
    if approve_reviewed:
        for row in rows:
            if row["quality_status"] == "reviewed_candidate":
                row["quality_status"] = "approved"
                note = (row["review_note"] or "").strip()
                row["review_note"] = f"{note}; {PROMOTION_NOTE}" if note else PROMOTION_NOTE
                promoted.append(row["relative_path"])
    singles = singleton_groups(rows)
    by_species: dict[str, list[dict]] = {}
    for row in rows:
        by_species.setdefault(row["species_name"], []).append(row)
    selection: dict[str, list[str]] = {}
    for species in sorted(by_species):
        pool = [row for row in by_species[species]
                if row["quality_status"] == "approved" and row["group_id"] in singles
                and (present is None or row["data_relative_path"] in present)]
        if len(pool) < per_species:
            raise ValueError(f"{species}: only {len(pool)} approved single-group images, need {per_species}")
        batches: dict[str, list[dict]] = {}
        for row in pool:
            batches.setdefault(row["selection_source"] or "unknown", []).append(row)
        for candidates in batches.values():
            candidates.sort(key=lambda row: (rank(seed, row), row["relative_path"]))
        names = sorted(batches)
        picked: list[dict] = []
        while len(picked) < per_species:
            for batch in names:
                if batches[batch] and len(picked) < per_species:
                    picked.append(batches[batch].pop(0))
            if all(not candidates for candidates in batches.values()):
                raise ValueError(f"{species}: not enough approved single-group images per batch")
        selection[species] = sorted(row["relative_path"] for row in picked)
    chosen = {path for paths in selection.values() for path in paths}
    for row in rows:
        row["split"] = "test" if row["relative_path"] in chosen else "gallery"
    return selection, promoted


def report(rows, selection, promoted, *, seed, per_species, source):
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = counts.setdefault(row["species_name"], {"gallery": 0, "test": 0})
        entry[row["split"]] += 1
    return {
        "action": "apply", "seed": seed, "test_per_species": per_species,
        "source_manifest": source, "images": len(rows), "promoted_reviewed_candidates": promoted,
        "totals": {"gallery": sum(entry["gallery"] for entry in counts.values()),
                   "test": sum(entry["test"] for entry in counts.values())},
        "per_species": counts, "test": selection,
    }


def check(config, *, per_species_range=(MIN_TEST_PER_SPECIES, MAX_TEST_PER_SPECIES)) -> list[str]:
    problems: list[str] = []
    _, rows = load(config.data_root / "dataset512-left/manifest.csv")
    if not rows:
        return ["empty manifest"]
    seen = set()
    groups: dict[str, set[str]] = {}
    test_counts: dict[str, int] = {}
    by_path = {}
    for row in rows:
        path = row["relative_path"]
        if path in seen:
            problems.append(f"duplicate relative_path: {path}")
        seen.add(path)
        by_path[path] = row
        if not (config.data_root / row["data_relative_path"]).is_file():
            problems.append(f"manifest row without file: {row['data_relative_path']}")
        if row["split"] not in {"gallery", "test"}:
            problems.append(f"split must be gallery/test, got {row['split']!r}: {path}")
        if row["split"] == "test":
            test_counts[row["species_name"]] = test_counts.get(row["species_name"], 0) + 1
            if row["quality_status"] != "approved":
                problems.append(f"test image is not approved: {path}")
        groups.setdefault(row["group_id"], set()).add(row["split"])
    for species in sorted({row["species_name"] for row in rows}):
        count = test_counts.get(species, 0)
        if not per_species_range[0] <= count <= per_species_range[1]:
            problems.append(f"test images outside {per_species_range[0]}-{per_species_range[1]}: {species} {count}")
    for group, splits in groups.items():
        if len(splits) > 1:
            problems.append(f"group crosses splits: {group}")
    approved_gallery = sum(row["quality_status"] == "approved" and row["split"] == "gallery" for row in rows)
    if approved_gallery < 500:
        problems.append(f"approved gallery below acceptance minimum: {approved_gallery}")
    source = config.source_manifest_path
    if source.exists():
        _, runtime = load(source)
        if {row["relative_path"] for row in runtime} != {row["data_relative_path"] for row in rows}:
            problems.append("runtime source manifest paths differ from the selected dataset")
        for row in runtime:
            portable = by_path.get(row["data_relative_path"])
            expected = 'validation' if portable and config.pca_components and portable['split']=='test' else portable['split'] if portable else None
            if portable and row["split"] != expected:
                problems.append(f"runtime split differs: {row['data_relative_path']}")
    else:
        problems.append(f"missing runtime source manifest: {config.relative_to_data(source)}")
    return problems


def export(config, output: Path, *, fields: list[str] | None = None,
           rows: list[dict] | None = None) -> dict:
    manifest = config.data_root / "dataset512-left/manifest.csv"
    if rows is None:
        fields, rows = load(manifest)
    test = [row for row in rows if row["split"] == "test"]
    if not test:
        raise ValueError("No test rows in the manifest; run --action apply first")
    copied = verified = 0
    for row in test:
        source = config.data_root / row["data_relative_path"]
        target = output / row["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256(source.read_bytes()).hexdigest()
        if target.exists():
            if sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Existing file differs from the dataset: {target}")
            verified += 1
            continue
        shutil.copy2(source, target)
        copied += 1
    with (output / "manifest-test.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(test[0]), lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(test)
    counts = Counter(row["species_name"] for row in test)
    (output / "README.md").write_text(
        "# Tập test của FaunaFind\n\n"
        f"{len(test)} ảnh RGB512 thuộc {len(counts)} loài, {len(test) // max(len(counts), 1)} ảnh mỗi loài "
        f"({', '.join(f'{name} {count}' for name, count in sorted(counts.items()))}).\n\n"
        "Đây là tập query đánh giá, tách từ data/dataset512-left bằng scripts/split_dataset.py\n"
        "(seed split-2026-10-20, chọn tất định, luân phiên giữa các đợt tuyển). Ảnh ở đây KHÔNG\n"
        "nằm trong CSDL truy hồi: gallery 781 ảnh approved là ứng viên tìm kiếm, 50 ảnh này chỉ\n"
        "dùng để truy vấn. manifest-test.csv giữ nguyên cột của manifest gốc (nguồn, giấy phép,\n"
        "checksum, split=test của nguồn gốc). Với profile PCA512 mặc định, 50 ảnh này đã dùng\n"
        "chọn số chiều nên có vai trò validation, không phải test độc lập. Chạy\n"
        "`python scripts/evaluate.py --split validation` sau khi CSDL có\n"
        "đủ gallery và mask đã duyệt; chi tiết ở artifacts/split-20261020/report.md.\n",
        encoding="utf-8")
    return {"output": config.relative_to_data(output), "images": len(test), "per_species": dict(counts),
            "copied": copied, "already_present_verified": verified,
            "manifest": config.relative_to_data(output / "manifest-test.csv")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--action", choices=["apply", "check", "export"], default="apply")
    parser.add_argument("--seed", default="split-2026-10-20", help="Chuỗi seed cho xếp hạng tất định")
    parser.add_argument("--test-per-species", type=int, default=5,
                        help=f"Số ảnh test mỗi loài ({MIN_TEST_PER_SPECIES}-{MAX_TEST_PER_SPECIES})")
    parser.add_argument("--approve-reviewed-candidates", action="store_true",
                        help="Chuyển reviewed_candidate thành approved kèm ghi chú")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in báo cáo, không ghi manifest")
    parser.add_argument("--report", type=Path, help="Ghi báo cáo JSON")
    parser.add_argument("--output", type=Path, default=Path("data/dataset512-test"),
                        help="Thư mục nhận bản sao tập test khi --action export")
    args = parser.parse_args()
    config = AppConfig.default()
    manifest = config.data_root / "dataset512-left/manifest.csv"
    if args.action == "check":
        problems = check(config)
        print(f"manifest={config.relative_to_data(manifest)} problems={len(problems)}")
        for problem in problems:
            print(" -", problem)
        raise SystemExit(1 if problems else 0)
    if args.action == "export":
        output = args.output if args.output.is_absolute() else config.project_root / args.output
        if not output.is_relative_to(config.project_root):
            raise SystemExit(f"--output must stay inside {config.project_root}")
        print(json.dumps(export(config, output), ensure_ascii=False))
        return
    if not MIN_TEST_PER_SPECIES <= args.test_per_species <= MAX_TEST_PER_SPECIES:
        raise SystemExit(f"--test-per-species must be within {MIN_TEST_PER_SPECIES}-{MAX_TEST_PER_SPECIES}")
    fields, rows = load(manifest)
    present = {row["data_relative_path"] for row in rows
               if (config.data_root / row["data_relative_path"]).is_file()}
    selection, promoted = assign(rows, seed=args.seed, per_species=args.test_per_species,
                                 approve_reviewed=args.approve_reviewed_candidates, present=present)
    result = report(rows, selection, promoted, seed=args.seed, per_species=args.test_per_species,
                    source=config.relative_to_data(manifest))
    if not args.dry_run:
        write(manifest, fields, rows)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["dry_run"] = args.dry_run
    print(json.dumps({key: result[key] for key in ("seed", "test_per_species", "images", "totals", "dry_run")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
