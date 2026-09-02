#!/usr/bin/env python3
"""Freeze the read-only inputs for the conditional-GMM review namespace."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_SPECS = (
    (
        "primary_population",
        "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/population/population_primary_admitted.csv",
    ),
    (
        "population_build_manifest",
        "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/qa/population_build_manifest.json",
    ),
    (
        "population_independent_qa",
        "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/qa/population_independent_qa_result.json",
    ),
    (
        "doppler_provenance_result",
        "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/qa/doppler_provenance_result.json",
    ),
    (
        "selected_marginal_models",
        "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/model/selected_model_by_parameter.csv",
    ),
    (
        "selected_joint_dependence_models",
        "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/model/joint_dependence_models.csv",
    ),
    (
        "selected_joint_model_qa",
        "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/qa/joint_model_build_result.json",
    ),
)

PROTECTED_RELATIVE_PATHS = (
    Path("scenes"),
    Path("dataset"),
    Path("dataset_generation_logs"),
    Path("docs/vtc2027_spring/manuscript"),
    Path("docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v1"),
    Path("docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_output_isolated(project_root: Path, output_root: Path) -> None:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    if not output_root.is_relative_to(project_root):
        raise ValueError("output root must remain inside the project root")
    for protected_relative in PROTECTED_RELATIVE_PATHS:
        protected = (project_root / protected_relative).resolve()
        if output_root == protected or output_root.is_relative_to(protected):
            raise ValueError(f"output root is protected: {output_root}")


def build_inventory(project_root: Path, output_root: Path) -> dict[str, Any]:
    ensure_output_isolated(project_root, output_root)
    sources: list[dict[str, Any]] = []
    for role, relative_path in SOURCE_SPECS:
        path = (project_root / relative_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"required source is missing: {path}")
        if not path.is_relative_to(project_root):
            raise ValueError(f"source escaped project root: {path}")
        sources.append(
            {
                "role": role,
                "path": str(path),
                "relative_path": relative_path,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "read_only": True,
            }
        )
    return {
        "inventory_id": "vtc_stage3_urban_mountain_conditional_gmm_source_inventory_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root.resolve()),
        "output_root": str(output_root.resolve()),
        "source_count": len(sources),
        "sources": sources,
        "execution_policy": {
            "raw_iq_read": False,
            "matlab_started": False,
            "sage_started": False,
            "batch_started": False,
            "stage4_used": False,
            "formal_manuscript_modified": False,
            "v1_modified": False,
            "v2_modified": False,
            "evidence_matrix_modified": False,
            "handoff_modified": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    output_root = args.output_root.resolve()
    inventory_path = output_root / "provenance/source_inventory.json"
    if inventory_path.exists() and not args.overwrite:
        raise FileExistsError(f"inventory exists; use --overwrite: {inventory_path}")
    inventory = build_inventory(project_root, output_root)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
