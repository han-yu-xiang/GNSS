"""Independent, read-only QA for the environment/elevation path model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np

from scripts.analysis.channel_modeling.path_distribution_core import (
    ENVIRONMENTS,
    ELEVATION_BANDS,
    FIT_PARAMETERS,
    build_cell_coverage,
    load_frozen_config,
    load_path_observations,
    to_model_vector,
)


REQUIRED_OUTPUT_FILES: tuple[str, ...] = (
    "source_path_audit.csv",
    "cell_coverage.csv",
    "marginal_family_selection.csv",
    "global_environment_marginals.csv",
    "cell_distribution_parameters.csv",
    "environment_copula_parameters.csv",
    "cell_model_index.csv",
    "bootstrap_uncertainty.csv",
    "fit_diagnostics.csv",
    "sampling_contract.json",
    "model_manifest.json",
    "model_report.md",
    "build_receipt.json",
)


@dataclass(frozen=True)
class AuditResult:
    build_output_complete: str
    source_and_label_gate: str
    cell_coverage_gate: str
    marginal_fit_gate: str
    copula_gate: str
    grouped_validation_gate: str
    model_qa: str
    ready_for_darkroom_generator_integration: str
    checks: Mapping[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _finite(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _float(value: str, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric value for {field}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite numeric value for {field}")
    return number


def _bool_text(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _check_source_audit(model_dir: Path, observations: Sequence[Any]) -> None:
    rows = _read_csv(model_dir / "source_path_audit.csv")
    if len(rows) != len(observations):
        raise ValueError("source_path_audit row count mismatch")
    expected = {row.event_path_id: row for row in observations}
    seen: set[str] = set()
    for row in rows:
        event_path_id = row["event_path_id"]
        if event_path_id in seen or event_path_id not in expected:
            raise ValueError("source_path_audit identity mismatch or duplicate")
        seen.add(event_path_id)
        observation = expected[event_path_id]
        vector = to_model_vector(observation)
        if abs(_float(row["relative_delay_ns"], "relative_delay_ns") - vector.relative_delay_ns) > 1e-12:
            raise ValueError("source delay transform mismatch")
        if abs(_float(row["relative_doppler_hz"], "relative_doppler_hz") - vector.relative_doppler_hz) > 1e-12:
            raise ValueError("source signed Doppler transform mismatch")
        if abs(_float(row["relative_power_db"], "relative_power_db") - vector.relative_power_db) > 1e-12:
            raise ValueError("source power transform mismatch")
        expected_amplitude = 10.0 ** (vector.relative_power_db / 20.0)
        if abs(_float(row["relative_amplitude_linear"], "relative_amplitude_linear") - expected_amplitude) > 1e-12:
            raise ValueError("relative power was not converted with /20")
        if row["elevation_band"] != (observation.elevation_band or ""):
            raise ValueError("elevation assignment changed in model audit")
        if not _bool_text(row["geometry_join_valid"]) and observation.elevation_band is not None:
            raise ValueError("elevation-ready source row lost geometry validity")
    if seen != set(expected):
        raise ValueError("source_path_audit omitted source rows")


def _check_coverage(model_dir: Path, observations: Sequence[Any]) -> list[dict[str, str]]:
    expected_rows = build_cell_coverage(observations)
    expected = {
        (row.environment, row.elevation_band): row
        for row in expected_rows
    }
    rows = _read_csv(model_dir / "cell_coverage.csv")
    if len(rows) != 12:
        raise ValueError(f"expected 12 coverage cells, got {len(rows)}")
    seen = set()
    for row in rows:
        key = (row["environment"], row["elevation_band"])
        if key in seen or key not in expected:
            raise ValueError("cell coverage identity mismatch")
        seen.add(key)
        current = expected[key]
        if int(row["path_count"]) != current.path_count:
            raise ValueError(f"cell path count mismatch for {key}")
        if row["support_status"] != current.support_status:
            raise ValueError(f"cell support status mismatch for {key}")
    if seen != set(expected):
        raise ValueError("cell coverage omitted cells")
    return rows


def _check_selection(model_dir: Path) -> None:
    rows = _read_csv(model_dir / "marginal_family_selection.csv")
    selected = {parameter: 0 for parameter in FIT_PARAMETERS}
    for row in rows:
        if row["parameter"] not in selected:
            raise ValueError("unknown family-selection parameter")
        if int(row["held_out_scene_count"]) != 11:
            raise ValueError("family selection did not use all represented scene blocks")
        if _bool_text(row["row_random_split_used"]):
            raise ValueError("row-random family validation is not allowed")
        if _bool_text(row["selected"]):
            selected[row["parameter"]] += 1
    if selected != {parameter: 1 for parameter in FIT_PARAMETERS}:
        raise ValueError(f"family selection does not have one selected family per parameter: {selected}")


def _parse_parameters(row: Mapping[str, str]) -> dict[str, float]:
    try:
        parameters = json.loads(row["fit_parameters_json"])
    except json.JSONDecodeError as exc:
        raise ValueError("invalid fit parameter JSON") from exc
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError("empty fit parameters")
    result = {str(name): float(value) for name, value in parameters.items()}
    if not all(math.isfinite(value) for value in result.values()):
        raise ValueError("non-finite fit parameter")
    if result.get("scale", 1.0) <= 0.0:
        raise ValueError("non-positive scale")
    return result


def _check_marginals(model_dir: Path, coverage_rows: Sequence[Mapping[str, str]]) -> None:
    global_rows = _read_csv(model_dir / "global_environment_marginals.csv")
    cell_rows = _read_csv(model_dir / "cell_distribution_parameters.csv")
    if len(global_rows) != 15:
        raise ValueError(f"expected 15 global/environment marginals, got {len(global_rows)}")
    if len(cell_rows) != 36:
        raise ValueError(f"expected 36 cell marginals, got {len(cell_rows)}")
    for row in global_rows + cell_rows:
        if row["parameter"] not in FIT_PARAMETERS:
            raise ValueError("unknown marginal parameter")
        _parse_parameters(row)
    coverage = {(row["environment"], row["elevation_band"]): row for row in coverage_rows}
    environment_parameters: dict[tuple[str, str], dict[str, float]] = {}
    for row in global_rows:
        if row["scope"] == "environment":
            environment_parameters[(row["scope_id"], row["parameter"])] = _parse_parameters(row)
    empty_cells = {("Urban", "LOW"), ("Highway/Open", "LOW")}
    seen_empty = set()
    for row in cell_rows:
        environment, band = row["scope_id"].rsplit("__", 1)
        key = (environment, band)
        if key not in coverage:
            raise ValueError("cell marginal has unknown cell")
        parameters = _parse_parameters(row)
        if int(row["local_likelihood_row_count"]) != int(coverage[key]["path_count"]):
            raise ValueError(f"cell local count mismatch for {key}")
        if int(coverage[key]["path_count"]) == 0:
            seen_empty.add(key)
            if row["support_status"] != "PRIOR_ONLY" or row["parameter_source"] != "environment_parent_only":
                raise ValueError(f"empty cell is not PRIOR_ONLY: {key}")
            parent = environment_parameters[(environment, row["parameter"])]
            if parameters != parent:
                raise ValueError(f"empty cell does not inherit environment parent exactly: {key}")
        elif row["support_status"] == "PRIOR_ONLY":
            raise ValueError("non-empty cell incorrectly marked PRIOR_ONLY")
    if seen_empty != empty_cells:
        raise ValueError(f"prior-only cell set changed: {seen_empty}")


def _check_copulas(model_dir: Path, observations: Sequence[Any], eigenvalue_floor: float, denominator: float) -> None:
    rows = _read_csv(model_dir / "environment_copula_parameters.csv")
    if len(rows) != 5:
        raise ValueError("expected global plus four environment copula rows")
    names = [f"corr__{left}__{right}" for left in FIT_PARAMETERS for right in FIT_PARAMETERS]
    global_row = next((row for row in rows if row["scope"] == "global"), None)
    if global_row is None:
        raise ValueError("global copula row missing")
    for row in rows:
        matrix = np.array([[float(row[f"corr__{left}__{right}"]) for right in FIT_PARAMETERS] for left in FIT_PARAMETERS])
        if not np.all(np.isfinite(matrix)):
            raise ValueError("non-finite copula")
        if not np.allclose(matrix, matrix.T, atol=1e-12):
            raise ValueError("copula is not symmetric")
        if not np.allclose(np.diag(matrix), 1.0, atol=1e-12):
            raise ValueError("copula diagonal is not one")
        if float(np.min(np.linalg.eigvalsh(matrix))) < eigenvalue_floor - 1e-10:
            raise ValueError("copula is not PSD at the frozen floor")
        if row["scope"] == "environment":
            environment = row["environment"]
            n = sum(observation.environment == environment for observation in observations)
            expected_weight = n / (n + denominator)
            if abs(float(row["shrinkage_weight"]) - expected_weight) > 1e-12:
                raise ValueError(f"copula shrinkage weight mismatch for {environment}")
        else:
            if float(row["shrinkage_weight"]) != 1.0:
                raise ValueError("global copula shrinkage weight must be one")
    if len({row["environment"] for row in rows if row["scope"] == "environment"}) != 4:
        raise ValueError("environment copula rows incomplete")


def _check_diagnostics(model_dir: Path) -> None:
    rows = _read_csv(model_dir / "fit_diagnostics.csv")
    if len(rows) != 12:
        raise ValueError("expected diagnostics for all 12 cells")
    for row in rows:
        for field in ("finite_rate", "positive_delay_rate", "positive_amplitude_rate", "max_copula_abs_corr_delta", "max_marginal_cdf_ppf_error"):
            if not _finite(row[field]):
                raise ValueError(f"diagnostic field is non-finite: {field}")
        if row["diagnostic_status"] != "PASS":
            raise ValueError(f"predictive diagnostic failed for {row['cell_id']}")
        if float(row["finite_rate"]) != 1.0 or float(row["positive_delay_rate"]) != 1.0 or float(row["positive_amplitude_rate"]) != 1.0:
            raise ValueError(f"invalid diagnostic draw support for {row['cell_id']}")
        if float(row["max_copula_abs_corr_delta"]) > 0.05:
            raise ValueError(f"copula sampling deviation too large for {row['cell_id']}")
        if float(row["max_marginal_cdf_ppf_error"]) > 1e-8:
            raise ValueError(f"marginal normalization deviation too large for {row['cell_id']}")


def audit_model(
    project_root: Path,
    config_path: Path,
    model_dir: Path,
    *,
    allow_test_namespace: bool = False,
) -> AuditResult:
    root = project_root.resolve(strict=False)
    config_file = config_path.resolve(strict=False)
    target = model_dir.resolve(strict=False)
    if not target.is_dir():
        raise FileNotFoundError(target)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        if allow_test_namespace:
            relative = Path()
        else:
            raise ValueError("model output is outside project root") from exc
    if any(part.lower() in {"scenes", "sage_results"} for part in relative.parts):
        raise ValueError("model output is under a protected SAGE namespace")
    config = load_frozen_config(config_file)
    observations, source_audit = load_path_observations(root, config)
    manifest_path = target / "model_manifest.json"
    receipt_path = target / "build_receipt.json"
    if not manifest_path.is_file() or not receipt_path.is_file():
        raise ValueError("model manifest or build receipt is missing")
    for name in REQUIRED_OUTPUT_FILES:
        if not (target / name).is_file():
            raise ValueError(f"required output is missing: {name}")
    manifest = _read_json(manifest_path)
    receipt = _read_json(receipt_path)
    manifest_hash = _sha256(manifest_path)
    if receipt.get("model_manifest_sha256") != manifest_hash:
        raise ValueError("build receipt manifest hash mismatch")
    if manifest.get("config_sha256") != _sha256(config_file):
        raise ValueError("model config hash mismatch")
    if manifest.get("source_sha256", "").lower() != source_audit.source_sha256.lower():
        raise ValueError("model source hash mismatch")
    if manifest.get("gold_labels_used_for_selection") is not False or manifest.get("posterior_gold_used_for_selection") is not False:
        raise ValueError("gold leakage flag is not false")
    if manifest.get("execution_policy", {}).get("raw_iq_read") is not False:
        raise ValueError("raw-IQ execution flag is not false")
    if manifest.get("execution_policy", {}).get("matlab") is not False or manifest.get("execution_policy", {}).get("sage") is not False:
        raise ValueError("execution policy is not offline-only")
    protected_path = root / Path(str(config.protected_source["pipeline_relative_path"]))
    if _sha256(protected_path).lower() != str(config.protected_source["pipeline_sha256"]).lower():
        raise ValueError("protected pipeline hash changed")
    expected_counts = {
        "environment_ready_paths": source_audit.environment_ready_count,
        "elevation_ready_paths": source_audit.elevation_ready_count,
        "elevation_excluded_paths": source_audit.elevation_excluded_count,
    }
    if manifest.get("source_counts") != expected_counts:
        raise ValueError("source counts in manifest mismatch")
    hashes = manifest.get("output_hashes_excluding_manifest_and_receipt", {})
    for name, expected_hash in hashes.items():
        if not (target / name).is_file() or _sha256(target / name) != expected_hash:
            raise ValueError(f"output hash mismatch: {name}")
    _check_source_audit(target, observations)
    coverage_rows = _check_coverage(target, observations)
    _check_selection(target)
    _check_marginals(target, coverage_rows)
    _check_copulas(target, observations, config.copula_eigenvalue_floor, config.copula_shrinkage_denominator)
    _check_diagnostics(target)
    checks = {
        "source_counts": expected_counts,
        "cell_count": len(coverage_rows),
        "marginal_count": len(_read_csv(target / "cell_distribution_parameters.csv")),
        "prior_only_cells": ["Urban__LOW", "Highway/Open__LOW"],
        "manifest_sha256": manifest_hash,
        "source_sha256": source_audit.source_sha256,
        "protected_pipeline_sha256": str(config.protected_source["pipeline_sha256"]),
        "qa_draw_count": config.qa_draw_count,
        "bootstrap_replicates": config.bootstrap_replicates,
    }
    result = AuditResult(
        build_output_complete="PASS",
        source_and_label_gate="PASS",
        cell_coverage_gate="PASS",
        marginal_fit_gate="PASS",
        copula_gate="PASS",
        grouped_validation_gate="PASS_WITH_LIMITATIONS",
        model_qa="PASS_WITH_LIMITATIONS",
        ready_for_darkroom_generator_integration="NO",
        checks=checks,
    )
    qa_result = {
        "qa_version": "environment-elevation-path-model-independent-qa-v1",
        "created_utc": _utc_now(),
        "model_dir": str(target),
        "model_manifest_sha256": manifest_hash,
        "result": result.__dict__,
        "limitations": [
            "PRIOR_ONLY cells are inherited from environment parents and are not empirically validated.",
            "The output is a conditional confirmed-NLOS path layer, not a complete darkroom generator.",
            "Main-path gain, phase, lock-loss mapping, occurrence rate, path lifetime and absolute power remain deferred.",
        ],
    }
    (target / "independent_qa_result.json").write_text(
        json.dumps(qa_result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = [
        "# Independent QA — Environment × Elevation Path Distribution Model v1",
        "",
        "`MODEL_QA=PASS_WITH_LIMITATIONS`",
        "",
        "The frozen Stage4 path source, transforms, 12-cell coverage, 36 cell marginals, environment-level copulas, grouped family-selection metadata, deterministic diagnostics and output hashes passed independent checks.",
        "",
        f"Model manifest SHA-256: `{manifest_hash}`",
        f"Source SHA-256: `{source_audit.source_sha256}`",
        "",
        "The two empty cells, Urban–LOW and Highway/Open–LOW, are `PRIOR_ONLY`; they are not empirical observations. The layer is not ready for direct darkroom-generator integration until the separate main-path, phase, lock-loss, occurrence/path-count and fixed-output composition decisions are completed.",
        "",
    ]
    (target / "independent_qa_report.md").write_text("\n".join(report), encoding="utf-8")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = audit_model(args.project_root, args.config, args.model_dir)
        print(json.dumps(result.__dict__, indent=2, sort_keys=True, default=str))
        print(f"MODEL_QA={result.model_qa}")
        return 0
    except Exception as exc:
        print(f"MODEL_QA_REJECTED={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
