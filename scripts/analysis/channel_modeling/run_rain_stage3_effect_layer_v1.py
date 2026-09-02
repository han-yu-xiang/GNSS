"""Build the frozen Stage3 Rain effect layer and eight darkroom tables.

This is a pure-Python postprocessor.  It reads only the nine explicitly
listed, already audited Stage3 CSV artifacts and the v2.2 canonical export
manifest.  It never reads raw IQ, Stage4, or MATLAB outputs for selection.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rain_stage3_effect_layer_v1 import (
    build_stage3_episodes,
    fit_rain_effect_model,
    load_stage3_evidence,
    sha256_file,
    write_collection,
)


KERNEL_SOURCE = Path(__file__).with_name("rain_stage3_effect_layer_v1.py")
RUNNER_SOURCE = Path(__file__)
COLLECTION_ID = "rain_effect_layer_stage3_v1_20260830_r1"


def _task_specs(project_root: Path) -> list[dict[str, Any]]:
    rows = [
        ("Clear", "F1023_clear", "G24", 10),
        ("Clear", "F1023_clear", "G29", 3),
        ("Clear", "F1023_clear", "G13", 8),
        ("Clear", "F1023_clear", "G12", 11),
        ("MidRain", "F1023_midrain", "G24", 8),
        ("MidRain", "F1023_midrain", "G20", 9),
        ("HeavyRain", "F1023_heavyrain", "G02", 1),
        ("HeavyRain", "F1023_heavyrain", "G31", 4),
        ("HeavyRain", "F1023_heavyrain", "G01", 7),
    ]
    specs: list[dict[str, Any]] = []
    for weather, scene, prn, channel in rows:
        task_id = f"{scene}__{prn}__ch{channel}"
        result_dir = project_root / "scenes" / scene / "sage_results" / "rain_sage_rerun_v1_20260827_r4" / prn
        specs.append(
            {
                "task_id": task_id,
                "weather": weather,
                "scene_id": scene,
                "prn": prn,
                "tracking_channel": channel,
                "stage3_persistence": str(result_dir / "stage3_persistence.csv"),
                "stage3_reliable_centers": str(result_dir / "stage3_reliable_centers.csv"),
            }
        )
    return specs


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_inputs(specs: list[dict[str, Any]], export_manifest: Path) -> None:
    if not export_manifest.is_file():
        raise FileNotFoundError(export_manifest)
    for spec in specs:
        for key in ("stage3_persistence", "stage3_reliable_centers"):
            path = Path(spec[key])
            if not path.is_file():
                raise FileNotFoundError(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--base-export-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--master-seed", type=int, default=20260830)
    parser.add_argument("--layer-weather", choices=("RainPooled", "MidRain", "HeavyRain"), default="RainPooled")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    output_dir = (args.output_dir or (project_root / "dataset_generation_logs" / "channel_modeling" / COLLECTION_ID)).resolve()
    export_manifest = args.base_export_manifest.resolve()
    specs = _task_specs(project_root)
    _validate_inputs(specs, export_manifest)
    evidence = load_stage3_evidence(specs)
    evidence = build_stage3_episodes(evidence, persistence_radius=2)
    model = fit_rain_effect_model(evidence)

    run_manifest = {
        "run_schema_version": "rain-stage3-effect-layer-run-1",
        "run_id": output_dir.name,
        "created_utc": _utc_now(),
        "project_root": str(project_root),
        "task_count": len(specs),
        "tasks": [
            {
                **spec,
                "stage3_persistence_sha256": sha256_file(Path(spec["stage3_persistence"])),
                "stage3_reliable_centers_sha256": sha256_file(Path(spec["stage3_reliable_centers"])),
            }
            for spec in specs
        ],
        "base_export_manifest": str(export_manifest),
        "base_export_manifest_sha256": sha256_file(export_manifest),
        "output_namespace": str(output_dir),
        "master_seed": args.master_seed,
        "layer_weather": args.layer_weather,
        "kernel_source": str(KERNEL_SOURCE),
        "kernel_source_sha256": sha256_file(KERNEL_SOURCE),
        "runner_source": str(RUNNER_SOURCE),
        "runner_source_sha256": sha256_file(RUNNER_SOURCE),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "stage4_used_for_fit": False,
        "gold_labels_used_for_selection": False,
        "new_only": True,
        "resume_allowed": False,
    }
    collection = write_collection(
        output_dir,
        export_manifest_path=export_manifest,
        evidence=evidence,
        model=model,
        master_seed=args.master_seed,
        layer_weather=args.layer_weather,
    )
    (output_dir / "rain_effect_layer_run_manifest.json").write_bytes(_canonical_json(run_manifest))
    run_manifest_sha = sha256_file(output_dir / "rain_effect_layer_run_manifest.json")
    (output_dir / "rain_effect_layer_run_manifest.sha256").write_text(f"{run_manifest_sha}  rain_effect_layer_run_manifest.json\n", encoding="ascii")
    summary = {
        "run_manifest_sha256": run_manifest_sha,
        "collection_manifest_sha256": collection["manifest_sha256"],
        "evidence_rows": len(evidence),
        "episode_count": len({row["episode_id"] for row in evidence}),
        "table_count": collection["table_count"],
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "gold_labels_used_for_selection": False,
    }
    (output_dir / "rain_effect_layer_build_summary.json").write_bytes(_canonical_json(summary))
    print(f"OUTPUT_NAMESPACE={output_dir}")
    print(f"EVIDENCE_ROWS={len(evidence)}")
    print(f"EPISODES={summary['episode_count']}")
    print(f"TABLES={collection['table_count']}")
    print(f"RUN_MANIFEST_SHA256={run_manifest_sha}")
    print(f"COLLECTION_MANIFEST_SHA256={collection['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
