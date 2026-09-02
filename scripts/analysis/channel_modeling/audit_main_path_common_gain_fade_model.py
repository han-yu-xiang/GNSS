"""Independent, read-only QA for the common-gain/fade model.

The auditor deliberately does not import the builder's fitting functions and
does not read raw IQ, Stage1--Stage4 outputs, MATLAB files, or production
artifacts.  It verifies the frozen source contract, re-reads the tracking
inputs through the existing read-only MAT reader, recomputes structural
counts/state semantics, and checks the published model and hashes.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .main_path_gain_core import (
        ENVIRONMENTS,
        ELEVATION_BANDS,
        GainFadeConfig,
        build_analysis_grid,
        compute_local_upper_baseline,
        extract_fade_events,
        fit_latent_correlation_time,
        json_safe,
        read_csv_rows,
        read_tracking_observation,
        resolve_gain_model_runs,
        sha256_file,
    )
except ImportError:
    from scripts.analysis.channel_modeling.main_path_gain_core import (
        ENVIRONMENTS,
        ELEVATION_BANDS,
        GainFadeConfig,
        build_analysis_grid,
        compute_local_upper_baseline,
        extract_fade_events,
        fit_latent_correlation_time,
        json_safe,
        read_csv_rows,
        read_tracking_observation,
        resolve_gain_model_runs,
        sha256_file,
    )


REQUIRED_OUTPUT_FILES: tuple[str, ...] = (
    "source_preflight.csv",
    "geometry_join_coverage.csv",
    "common_gain_analysis_grid.csv.gz",
    "common_gain_run_summary.csv",
    "fade_event_catalog.csv",
    "cell_coverage.csv",
    "family_selection.csv",
    "common_gain_marginal_parameters.csv",
    "common_gain_temporal_parameters.csv",
    "fade_entry_rate_parameters.csv",
    "fade_depth_duration_parameters.csv",
    "main_path_common_gain_fade_model.json",
    "qa_draw_summary.csv",
    "model_manifest.json",
    "run_receipt.json",
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_grid_rows(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fail(checks: dict[str, Any], name: str, reason: str) -> None:
    checks[name] = {"status": "FAIL", "reason": reason}


def _pass(checks: dict[str, Any], name: str, details: Mapping[str, Any] | None = None) -> None:
    checks[name] = {"status": "PASS", **(dict(details) if details else {})}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check_namespace(project_root: Path, model_dir: Path, checks: dict[str, Any]) -> None:
    root = (project_root / "dataset_generation_logs" / "channel_modeling").resolve()
    target = model_dir.resolve()
    if not _is_within(target, root):
        _fail(checks, "namespace_isolation", "model namespace is outside dataset_generation_logs/channel_modeling")
        return
    relative = {part.lower() for part in target.relative_to(root).parts}
    if "scenes" in relative or "sage_results" in relative:
        _fail(checks, "namespace_isolation", "model namespace contains protected scenes/sage_results component")
        return
    _pass(checks, "namespace_isolation", {"model_dir": str(target)})


def _check_receipt_and_policy(model_dir: Path, checks: dict[str, Any]) -> dict[str, Any]:
    receipt = _read_json(model_dir / "run_receipt.json")
    required_false = ("raw_iq_read", "matlab_executed", "sage_executed", "batch_executed")
    bad = [name for name in required_false if receipt.get(name) is not False]
    if receipt.get("gold_labels_used_for_selection") is not False:
        bad.append("gold_labels_used_for_selection")
    if bad:
        _fail(checks, "execution_policy", f"forbidden execution/policy flags are not false: {bad}")
    else:
        _pass(checks, "execution_policy", {"raw_iq_read": False, "matlab_executed": False, "sage_executed": False, "batch_executed": False, "gold_labels_used_for_selection": False})
    if receipt.get("status") != "completed":
        _fail(checks, "run_receipt", f"receipt status is {receipt.get('status')!r}")
    elif not receipt.get("output_files") or not receipt.get("output_hashes"):
        _fail(checks, "run_receipt", "receipt lacks complete output file/hash inventory")
    else:
        _pass(checks, "run_receipt", {"receipt_status": receipt.get("status"), "output_file_count": len(receipt["output_files"])})
    receipt_hash_failures: list[str] = []
    for name, expected in dict(receipt.get("output_hashes", {})).items():
        target = model_dir / str(name)
        if not target.is_file() or sha256_file(target).lower() != str(expected).lower():
            receipt_hash_failures.append(str(name))
    if receipt_hash_failures:
        _fail(checks, "receipt_output_hashes", f"receipt output hash mismatch: {receipt_hash_failures}")
    else:
        _pass(checks, "receipt_output_hashes", {"checked_count": len(receipt.get("output_hashes", {}))})
    return receipt


def _check_file_set(model_dir: Path, checks: dict[str, Any]) -> None:
    missing = [name for name in REQUIRED_OUTPUT_FILES if not (model_dir / name).is_file() or (model_dir / name).stat().st_size <= 0]
    if missing:
        _fail(checks, "output_completeness", f"missing or empty outputs: {missing}")
    else:
        _pass(checks, "output_completeness", {"required_file_count": len(REQUIRED_OUTPUT_FILES)})


def _check_manifest_hashes(project_root: Path, model_dir: Path, config: GainFadeConfig, checks: dict[str, Any]) -> dict[str, Any]:
    manifest = _read_json(model_dir / "model_manifest.json")
    if manifest.get("model_id") != config.model_id or manifest.get("model_version") != config.model_version:
        _fail(checks, "manifest_identity", "model id/version does not match frozen config")
    else:
        _pass(checks, "manifest_identity", {"model_id": manifest.get("model_id"), "model_version": manifest.get("model_version")})
    if manifest.get("config_sha256") != sha256_file(project_root / "configs" / "channel_modeling" / "main_path_common_gain_fade_v1.json"):
        _fail(checks, "config_hash", "published config hash mismatch")
    else:
        _pass(checks, "config_hash", {"sha256": manifest.get("config_sha256")})
    output_hashes = manifest.get("output_hashes", {})
    mismatches: list[str] = []
    for name, expected in output_hashes.items():
        target = model_dir / name
        if not target.is_file() or sha256_file(target).lower() != str(expected).lower():
            mismatches.append(name)
    if mismatches:
        _fail(checks, "output_hashes", f"output hash mismatch: {mismatches}")
    else:
        _pass(checks, "output_hashes", {"checked_count": len(output_hashes)})
    source_contract = manifest.get("source_contract")
    if source_contract != dict(config.source):
        _fail(checks, "source_contract", "manifest source contract differs from frozen config")
    else:
        _pass(checks, "source_contract")
    if manifest.get("execution_policy", {}).get("gold_labels_used_for_selection") is not False:
        _fail(checks, "manifest_gold_policy", "manifest permits gold labels for selection")
    else:
        _pass(checks, "manifest_gold_policy")
    source_preflight_path = model_dir / "source_preflight.csv"
    if sha256_file(source_preflight_path).lower() != str(manifest.get("source_preflight_sha256", "")).lower():
        _fail(checks, "source_preflight_hash", "source_preflight hash does not match model manifest")
    else:
        _pass(checks, "source_preflight_hash")
    code_paths = {
        "core": project_root / "scripts" / "analysis" / "channel_modeling" / "main_path_gain_core.py",
        "builder": project_root / "scripts" / "analysis" / "channel_modeling" / "build_main_path_common_gain_fade_model.py",
        "config": project_root / "configs" / "channel_modeling" / "main_path_common_gain_fade_v1.json",
    }
    code_failures = [
        name for name, path in code_paths.items()
        if not path.is_file() or sha256_file(path).lower() != str(manifest.get("code_hashes", {}).get(name, "")).lower()
    ]
    if code_failures:
        _fail(checks, "code_hashes", f"current code/config hash differs from manifest: {code_failures}")
    else:
        _pass(checks, "code_hashes", {name: str(manifest["code_hashes"][name]) for name in code_paths})
    protected_path = project_root / Path(str(config.protected_source.get("pipeline_relative_path", "")))
    protected_expected = str(config.protected_source.get("pipeline_sha256", ""))
    if not protected_path.is_file() or sha256_file(protected_path).lower() != protected_expected.lower():
        _fail(checks, "protected_pipeline_hash", "protected production pipeline hash mismatch")
    else:
        _pass(checks, "protected_pipeline_hash", {"sha256": protected_expected})
    return manifest


def _check_source_preflight(project_root: Path, config: GainFadeConfig, model_dir: Path, checks: dict[str, Any]) -> None:
    rows = _read_csv(model_dir / "source_preflight.csv")
    parent_keys = {key for key in config.source if key.endswith("relative_path")}
    actual_parent_keys = {row.get("source_key", "") for row in rows if row.get("source_key", "") in parent_keys}
    if actual_parent_keys != parent_keys:
        _fail(checks, "parent_source_preflight", f"expected parent source keys {sorted(parent_keys)}, got {sorted(actual_parent_keys)}")
        return
    failures: list[str] = []
    for row in rows:
        key = row.get("source_key", "")
        if key in parent_keys:
            path = project_root / Path(str(config.source[key]))
            expected = str(config.source.get(key.replace("relative_path", "sha256"), ""))
            if not path.is_file() or sha256_file(path).lower() != expected.lower():
                failures.append(key)
    tracking_rows = [row for row in rows if row.get("source_key", "").startswith("tracking:")]
    if len(tracking_rows) != 63:
        failures.append(f"tracking_count={len(tracking_rows)}")
    if failures:
        _fail(checks, "source_preflight", "; ".join(failures))
    else:
        _pass(checks, "source_preflight", {"eligible_runs": len(tracking_rows), "parent_sources": len(parent_keys)})


def _check_tracking_preflight(model_dir: Path, runs: Sequence[Any], checks: dict[str, Any]) -> None:
    rows = _read_csv(model_dir / "source_preflight.csv")
    expected = {run.run_id: run for run in runs}
    failures: list[str] = []
    seen: set[str] = set()
    for row in rows:
        key = row.get("source_key", "")
        if not key.startswith("tracking:"):
            continue
        run_id = key.split(":", 1)[1]
        if run_id in seen or run_id not in expected:
            failures.append(run_id)
            continue
        seen.add(run_id)
        run = expected[run_id]
        path = run.tracking_path
        if not path.is_file() or sha256_file(path).lower() != run.tracking_sha256.lower():
            failures.append(f"{run_id}:source_hash")
        if str(row.get("sha256", "")).lower() != run.tracking_sha256.lower():
            failures.append(f"{run_id}:recorded_hash")
        if str(row.get("path", "")) != str(path):
            failures.append(f"{run_id}:path")
    if len(seen) != len(expected):
        failures.append(f"missing_tracking_rows={len(expected) - len(seen)}")
    if failures:
        _fail(checks, "tracking_preflight", "; ".join(failures[:10]))
    else:
        _pass(checks, "tracking_preflight", {"rehashed_runs": len(seen)})


def _check_grid_and_events(project_root: Path, config: GainFadeConfig, model_dir: Path, checks: dict[str, Any]) -> dict[str, Any]:
    runs = resolve_gain_model_runs(project_root, config)
    all_rows: list[Any] = []
    all_events: list[Any] = []
    expected_summaries: dict[str, dict[str, Any]] = {}
    for run in runs:
        observation = read_tracking_observation(run, sample_rate_hz=config.sample_rate_hz)
        rows = build_analysis_grid(observation, bin_ms=config.analysis_bin_ms)
        compute_local_upper_baseline(
            rows,
            window_s=config.baseline_window_s,
            quantile=config.baseline_quantile,
            short_segment_min_duration_s=config.short_segment_min_duration_s,
            minimum_points=config.minimum_baseline_points,
        )
        result = extract_fade_events(rows, config)
        all_rows.extend(rows)
        all_events.extend(result.events)
        expected_summaries[run.run_id] = {"grid": len(rows), "events": len(result.events), "missing": result.missing_rows}
    grid_rows = _read_grid_rows(model_dir / "common_gain_analysis_grid.csv.gz")
    event_rows = _read_csv(model_dir / "fade_event_catalog.csv")
    if len(grid_rows) != len(all_rows):
        _fail(checks, "analysis_grid_count", f"published={len(grid_rows)} recomputed={len(all_rows)}")
    else:
        _pass(checks, "analysis_grid_count", {"rows": len(grid_rows), "runs": len(runs)})
    if len(event_rows) != len(all_events):
        _fail(checks, "fade_event_count", f"published={len(event_rows)} recomputed={len(all_events)}")
    else:
        _pass(checks, "fade_event_count", {"events": len(event_rows)})
    nonfinite = [
        row.get("time_s", "")
        for row in grid_rows
        if not _finite(row.get("time_s")) or not _finite(row.get("common_gain_db")) and row.get("common_gain_db") not in ("", None)
    ]
    if nonfinite:
        _fail(checks, "grid_numeric_finiteness", f"non-finite grid values: {len(nonfinite)}")
    else:
        _pass(checks, "grid_numeric_finiteness")
    invalid_censor = [row for row in event_rows if _bool(row.get("right_censored")) and not row.get("censor_reason")]
    if invalid_censor:
        _fail(checks, "censor_semantics", "right-censored event lacks censor_reason")
    else:
        _pass(checks, "censor_semantics", {"right_censored_events": sum(_bool(row.get("right_censored")) for row in event_rows)})
    return {"runs": runs, "rows": all_rows, "events": all_events, "expected_summaries": expected_summaries}


def _check_geometry_and_cells(model_dir: Path, checks: dict[str, Any]) -> None:
    geometry = _read_csv(model_dir / "geometry_join_coverage.csv")
    if len(geometry) != 63:
        _fail(checks, "geometry_coverage", f"expected 63 run rows, got {len(geometry)}")
    elif any(not _finite(row.get("geometry_coverage_fraction")) for row in geometry):
        _fail(checks, "geometry_coverage", "non-finite geometry coverage")
    else:
        _pass(checks, "geometry_coverage", {"run_rows": len(geometry), "valid_grid_rows": sum(int(row.get("valid_geometry_rows", 0)) for row in geometry)})
    cells = _read_csv(model_dir / "cell_coverage.csv")
    keys = {(row.get("environment"), row.get("elevation_band")) for row in cells}
    expected = {(environment, band) for environment in ENVIRONMENTS for band in ELEVATION_BANDS}
    if keys != expected or len(cells) != 12:
        _fail(checks, "cell_coverage", f"expected 12 environment/elevation cells, got {len(cells)}")
    else:
        _pass(checks, "cell_coverage", {"cells": len(cells)})
    if any(row.get("gain_support_status") == "PRIOR_ONLY" and int(row.get("gain_direct_rows", 0)) != 0 for row in cells):
        _fail(checks, "sparse_cell_semantics", "non-empty gain cell marked PRIOR_ONLY")
    else:
        _pass(checks, "sparse_cell_semantics")


def _check_family_and_parameters(model_dir: Path, checks: dict[str, Any]) -> None:
    selection = _read_csv(model_dir / "family_selection.csv")
    expected = {"normal_gain_db", "fade_depth_db", "fade_duration_s"}
    selected = {row.get("parameter") for row in selection if row.get("status") in {"SELECTED", "PRIOR_ONLY_NO_EVENTS", "INCONCLUSIVE"}}
    if not expected.issubset(selected):
        _fail(checks, "family_selection", f"family-selection parameters missing: {sorted(expected - selected)}")
    elif any(_bool(row.get("row_random_split_used")) for row in selection):
        _fail(checks, "family_selection", "row-random split was used")
    else:
        _pass(checks, "family_selection", {"parameters": sorted(selected)})
    parameter_files = ("common_gain_marginal_parameters.csv", "fade_depth_duration_parameters.csv")
    bad: list[str] = []
    for name in parameter_files:
        for row in _read_csv(model_dir / name):
            try:
                parameters = json.loads(row.get("parameters", "{}"))
            except json.JSONDecodeError:
                bad.append(f"{name}:invalid_json")
                continue
            if not isinstance(parameters, dict) or not parameters or not all(_finite(value) for value in parameters.values()):
                bad.append(f"{name}:nonfinite_or_empty")
    if bad:
        _fail(checks, "parameter_finiteness", "; ".join(bad[:10]))
    else:
        _pass(checks, "parameter_finiteness")


def _check_temporal_and_draws(model_dir: Path, checks: dict[str, Any]) -> None:
    temporal = _read_csv(model_dir / "common_gain_temporal_parameters.csv")
    bad = [row for row in temporal if not _finite(row.get("tau_s")) or float(row.get("tau_s")) <= 0]
    if bad:
        _fail(checks, "temporal_parameters", f"invalid tau rows: {len(bad)}")
    else:
        _pass(checks, "temporal_parameters", {"rows": len(temporal)})
    draws = _read_csv(model_dir / "qa_draw_summary.csv")
    if len(draws) != 12 or any(row.get("finite") != "1" for row in draws):
        _fail(checks, "qa_draws", f"expected 12 finite cell draw summaries, got {len(draws)}")
    elif any(not _finite(row.get("gain_p10_db")) or not _finite(row.get("gain_p90_db")) for row in draws):
        _fail(checks, "qa_draws", "non-finite draw quantile")
    else:
        _pass(checks, "qa_draws", {"cells": len(draws)})


def _write_report(model_dir: Path, result: Mapping[str, Any]) -> None:
    checks = result["checks"]
    failed = [name for name, value in checks.items() if value.get("status") != "PASS"]
    report_lines = [
        "# Main Path Common Gain/Fade Model v1 Independent QA",
        "",
        f"- Generated UTC: {result['generated_utc']}",
        f"- Model namespace: `{model_dir}`",
        f"- Overall status: **{'PASS_WITH_LIMITATIONS' if not failed else 'FAIL'}**",
        "- Raw IQ read: `NO`",
        "- MATLAB/SAGE/batch executed: `NO`",
        "- Gold labels used for selection: `false`",
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for name, value in checks.items():
        details = {key: item for key, item in value.items() if key not in {"status"}}
        report_lines.append(f"| `{name}` | **{value.get('status')}** | `{json.dumps(json_safe(details), ensure_ascii=False, sort_keys=True)}` |")
    report_lines.extend([
        "",
        "## Interpretation",
        "",
        "The common gain is a run-normalized tracking C/N0 proxy, not calibrated RF power and not an isolated physical LOS amplitude. LOCK_BAD and continuity losses are not treated as exact fade depth. Sparse geometry cells inherit parent parameters and remain explicitly support-limited.",
        "",
        "The output is a bounded modeling layer. It does not complete the NLOS activation, phase, lock-recovery, or four-path darkroom generator.",
        "",
    ])
    (model_dir / "independent_qa_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    (model_dir / "independent_qa_result.json").write_text(json.dumps(json_safe(result), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def audit_model(project_root: Path, model_dir: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    model_dir = model_dir.resolve()
    if not model_dir.is_dir():
        raise FileNotFoundError(model_dir)
    checks: dict[str, Any] = {}
    _check_namespace(project_root, model_dir, checks)
    manifest_path = model_dir / "model_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    try:
        preliminary_manifest = _read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _fail(checks, "manifest_structure", str(exc))
        return {
            "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "overall_status": "FAIL",
            "gold_labels_used_for_selection": False,
            "checks": checks,
        }
    required_manifest_keys = {"model_id", "model_version", "output_namespace", "config_sha256", "source_preflight_sha256", "code_hashes", "output_hashes", "execution_policy", "source_contract"}
    if not required_manifest_keys.issubset(preliminary_manifest):
        _fail(checks, "manifest_structure", f"missing manifest keys: {sorted(required_manifest_keys - set(preliminary_manifest))}")
        return {
            "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "overall_status": "FAIL",
            "gold_labels_used_for_selection": False,
            "checks": checks,
        }
    if Path(str(preliminary_manifest.get("output_namespace", ""))).resolve() != model_dir:
        _fail(checks, "manifest_output_namespace", "manifest output namespace does not match audited directory")
    else:
        _pass(checks, "manifest_output_namespace")
    _check_file_set(model_dir, checks)
    config_path = project_root / "configs" / "channel_modeling" / "main_path_common_gain_fade_v1.json"
    config = GainFadeConfig.from_json(config_path)
    receipt = _check_receipt_and_policy(model_dir, checks)
    manifest = _check_manifest_hashes(project_root, model_dir, config, checks)
    _check_source_preflight(project_root, config, model_dir, checks)
    recomputed = _check_grid_and_events(project_root, config, model_dir, checks)
    _check_tracking_preflight(model_dir, recomputed["runs"], checks)
    _check_geometry_and_cells(model_dir, checks)
    _check_family_and_parameters(model_dir, checks)
    _check_temporal_and_draws(model_dir, checks)
    failed = [name for name, value in checks.items() if value.get("status") != "PASS"]
    result: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "overall_status": "FAIL" if failed else "PASS_WITH_LIMITATIONS",
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "matlab_executed": False,
        "sage_executed": False,
        "batch_executed": False,
        "checks": checks,
        "counts": {
            "eligible_runs": len(recomputed["runs"]),
            "analysis_grid_rows": len(recomputed["rows"]),
            "fade_events": len(recomputed["events"]),
            "published_output_hashes": len(manifest.get("output_hashes", {})),
        },
        "receipt_status": receipt.get("status"),
        "model_manifest_sha256": sha256_file(model_dir / "model_manifest.json"),
        "protected_pipeline_sha256": str(config.protected_source.get("pipeline_sha256", "")),
    }
    _write_report(model_dir, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit_model(args.project_root, args.model_dir)
    print(f"MODEL_QA_STATUS={result['overall_status']}")
    print(f"MODEL_QA_REPORT={args.model_dir.resolve() / 'independent_qa_report.md'}")
    return 0 if result["overall_status"] != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
