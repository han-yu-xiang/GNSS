"""Prepare the immutable eight-request v2.2 environment/quality pilot matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_generator_v2_2_core import ENVIRONMENTS, V22_MATRIX_ROOT, V22_REQUEST_ROOT, V22_RUN_ROOT, canonical_json_bytes, load_v22_config
    from .prepare_darkroom_generator_v2_2_request import PAIRING_IDS, build_v22_request_payload, write_v22_request_namespace
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import ENVIRONMENTS, V22_MATRIX_ROOT, V22_REQUEST_ROOT, V22_RUN_ROOT, canonical_json_bytes, load_v22_config
    from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_2_request import PAIRING_IDS, build_v22_request_payload, write_v22_request_namespace


MATRIX_ID = "environment_quality_pair_20s_v2_2_20260827"
MATRIX_ROOT_NAME = MATRIX_ID
QUALITY_SEQUENCE = ("GOOD_TRACKED_BASELINE", "POOR_CONDITIONAL")
QUALITY_SHORT = {"GOOD_TRACKED_BASELINE": "good", "POOR_CONDITIONAL": "poor"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve(project_root: Path, relative: str) -> Path:
    root = project_root.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {relative}") from exc
    return target


def _direct_child(path: Path, root: Path, name: str) -> bool:
    try:
        return path.resolve().parent == root.resolve() and path.resolve().name == name
    except OSError:
        return False


def build_matrix(
    *,
    project_root: Path,
    config_path: Path,
    matrix_id: str = MATRIX_ID,
    request_tag: str = "",
    duration_ms: int = 20_000,
    master_seed: int = 20_260_827,
) -> tuple[Path, Path, str, list[dict[str, Any]]]:
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    matrix_root = _resolve(project_root, V22_MATRIX_ROOT)
    matrix_dir = matrix_root / matrix_id
    request_root = _resolve(project_root, V22_REQUEST_ROOT)
    if matrix_dir.exists():
        raise FileExistsError(f"matrix namespace already exists: {matrix_dir}")
    matrix_root.mkdir(parents=True, exist_ok=True)
    config = load_v22_config(config_path, project_root)
    if tuple(config.environments) != ENVIRONMENTS:
        raise ValueError("environment order does not match frozen matrix")
    if request_tag and (not request_tag.replace("-", "").replace("_", "").isalnum()):
        raise ValueError("request_tag must contain only letters, digits, '-' or '_'")
    matrix_dir.mkdir()
    rows: list[dict[str, Any]] = []
    row_number = 0
    try:
        for environment in ENVIRONMENTS:
            pairing_id = PAIRING_IDS[environment]
            normalized = environment.lower().replace("/", "-").replace(" ", "-")
            for quality_mode in QUALITY_SEQUENCE:
                row_number += 1
                tag_part = f"_{request_tag}" if request_tag else ""
                request_id = f"{normalized}_{QUALITY_SHORT[quality_mode]}_20s_v2_2{tag_part}_20260827"
                request_dir = request_root / request_id
                output_relative = f"{V22_RUN_ROOT}/{request_id}"
                payload = build_v22_request_payload(
                    project_root=project_root,
                    config_path=config_path,
                    request_id=request_id,
                    environment=environment,
                    quality_mode=quality_mode,
                    duration_ms=duration_ms,
                    master_seed=master_seed,
                    pairing_id=pairing_id,
                    simulation_id=request_id,
                    request_purpose="PILOT_20S_MATRIX",
                    output_namespace=output_relative,
                )
                request_path, request_sha = write_v22_request_namespace(request_dir, payload)
                output_dir = _resolve(project_root, output_relative)
                rows.append(
                    {
                        "matrix_id": matrix_id,
                        "matrix_row": row_number,
                        "accepted": True,
                        "rejected_reason": "",
                        "environment_class": environment,
                        "quality_mode": quality_mode,
                        "pairing_id": pairing_id,
                        "request_id": request_id,
                        "request_path": str(request_path),
                        "request_sha256": request_sha,
                        "output_namespace": output_relative,
                        "output_path": str(output_dir),
                        "output_absent_at_freeze": not output_dir.exists(),
                        "duration_ms": duration_ms,
                        "master_seed": master_seed,
                        "expected_rows": duration_ms * 12,
                        "new_only": True,
                        "resume_allowed": False,
                        "raw_iq_read": False,
                        "matlab": False,
                        "sage": False,
                        "batch": False,
                        "process_20_46_mhz": False,
                        "gold_labels_used_for_generation": False,
                    }
                )
    except Exception:
        # Preserve any partial request/matrix evidence.  No cleanup is
        # attempted; a subsequent run must use a new matrix id.
        raise
    matrix_csv = matrix_dir / "request_matrix.csv"
    fields = tuple(rows[0].keys()) if rows else ()
    with matrix_csv.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "matrix_schema_version": "darkroom-generator-matrix-2.2",
        "matrix_id": matrix_id,
        "created_utc": _utc_now(),
        "generator_version": config.generator_version,
        "generator_config_relative_path": config_path.relative_to(project_root).as_posix(),
        "generator_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "request_root_relative_path": V22_REQUEST_ROOT,
        "run_root_relative_path": V22_RUN_ROOT,
        "ordered_environments": list(ENVIRONMENTS),
        "ordered_quality_modes": list(QUALITY_SEQUENCE),
        "duration_ms": duration_ms,
        "master_seed": master_seed,
        "request_tag": request_tag,
        "accepted_count": len(rows),
        "rejected_count": 0,
        "request_matrix_relative_path": matrix_csv.relative_to(project_root).as_posix(),
        "request_rows": rows,
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "gold_labels_used_for_generation": False,
    }
    manifest_path = matrix_dir / "matrix_manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    digest_path = matrix_dir / "matrix_manifest.sha256"
    digest_path.write_text(digest + "\n", encoding="ascii", newline="\n")
    return matrix_csv, manifest_path, digest, rows


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--matrix-id", default=MATRIX_ID)
    parser.add_argument("--request-tag", default="")
    parser.add_argument("--duration-ms", type=int, default=20_000)
    parser.add_argument("--master-seed", type=int, default=20_260_827)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            config = load_v22_config(args.config.resolve(), args.project_root.resolve())
            print(json.dumps({"generator_id": config.model_id, "environments": list(config.environments), "quality_modes": list(QUALITY_SEQUENCE), "duration_ms": args.duration_ms, "master_seed": args.master_seed}, ensure_ascii=False, indent=2))
            return 0
        matrix_csv, manifest_path, digest, rows = build_matrix(
            project_root=args.project_root,
            config_path=args.config,
            matrix_id=args.matrix_id,
            request_tag=args.request_tag,
            duration_ms=args.duration_ms,
            master_seed=args.master_seed,
        )
        print(f"REQUEST_MATRIX={matrix_csv}")
        print(f"MATRIX_MANIFEST={manifest_path}")
        print(f"MATRIX_MANIFEST_SHA256={digest}")
        print(f"ACCEPTED_ROWS={len(rows)}")
        print("REJECTED_ROWS=0")
        return 0
    except Exception as exc:
        print(f"V22_MATRIX_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
