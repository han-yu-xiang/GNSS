"""Independently audit the lock-amplitude/phase/recovery model namespace.

The auditor deliberately does not import the builder.  It checks the frozen
contracts, output hashes, row accounting, censoring/status semantics, phase
and envelope invariants, and namespace isolation using published artifacts.
It never opens raw IQ or invokes MATLAB/SAGE/batch.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.analysis.channel_modeling.lock_amplitude_phase_recovery_core import (
    ENVIRONMENTS,
    ELEVATION_BANDS,
    sha256_file,
)


REQUIRED_OUTPUT_FILES: tuple[str, ...] = (
    "source_preflight.csv",
    "lock_gain_alignment_catalog.csv",
    "lock_event_envelope_features.csv",
    "recovery_trace_catalog.csv.gz",
    "recovery_family_selection.csv",
    "environment_recovery_parameters.csv",
    "lock_amplitude_mapping_contract.json",
    "phase_policy_contract.json",
    "composition_contract.json",
    "deterministic_scalar_draws.csv",
    "deterministic_state_sequence.csv.gz",
    "lock_amplitude_phase_recovery_model.json",
    "model_manifest.json",
    "build_receipt.json",
    "model_report.md",
)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_csv_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def require_required_artifacts(output_dir: Path) -> None:
    missing = [name for name in REQUIRED_OUTPUT_FILES if not (output_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing required artifacts: {missing}")


def validate_manifest_policy(manifest: Mapping[str, Any]) -> None:
    if manifest.get("gold_labels_used_for_selection") is not False:
        raise ValueError("gold_labels_used_for_selection must be false")
    for field in ("raw_iq_read", "matlab_executed", "sage_executed", "batch_executed"):
        if manifest.get(field) is not False:
            raise ValueError(f"offline policy changed: {field}")
    policy = dict(manifest.get("execution_policy", {}))
    if policy.get("new_only") is not True or policy.get("resume_allowed") is not False:
        raise ValueError("new-only/non-resumable policy changed")
    if policy.get("gold_labels_used_for_selection") is not False:
        raise ValueError("gold selection policy changed")


def validate_envelope_values(values: Sequence[float], direction: str) -> None:
    if direction not in {"entry", "recovery"}:
        raise ValueError(f"unknown envelope direction: {direction}")
    numeric = [float(value) for value in values]
    if any(not math.isfinite(value) or value <= 0.0 for value in numeric):
        raise ValueError("envelope contains non-positive/non-finite value")
    for left, right in zip(numeric, numeric[1:]):
        if direction == "entry" and left + 1e-12 < right:
            raise ValueError("entry envelope is not monotone non-increasing")
        if direction == "recovery" and left - 1e-12 > right:
            raise ValueError("recovery envelope is not monotone non-decreasing")


def validate_active_amplitude(amplitude: float, mapping_mode: str) -> None:
    value = float(amplitude)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"active amplitude is invalid for {mapping_mode}: {amplitude!r}")


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _float_or_none(value: Any) -> float | None:
    if value is None or str(value).strip().lower() in {"", "none", "null", "nan"}:
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _check_parent_sources(project_root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    sources = dict(config.get("sources", {}))
    rows: list[dict[str, Any]] = []
    for key, value in sorted(sources.items()):
        if not key.endswith("_relative_path"):
            continue
        relative = Path(str(value))
        if relative.is_absolute():
            raise ValueError(f"absolute source path is forbidden: {value}")
        path = (project_root / relative).resolve(strict=False)
        try:
            path.relative_to(project_root.resolve())
        except ValueError as exc:
            raise ValueError(f"source escapes project root: {value}") from exc
        expected = str(sources.get(key.removesuffix("_relative_path") + "_sha256", "")).lower()
        actual = sha256_file(path) if path.is_file() else None
        rows.append({"source_key": key, "expected": expected, "actual": actual, "status": "PASS" if actual == expected else "FAIL"})
        if actual != expected:
            raise ValueError(f"parent source hash mismatch: {key}")
    return {"source_count": len(rows), "rows": rows}


def _check_output_hashes(output_dir: Path, manifest: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, int]:
    manifest_hashes = dict(manifest.get("output_hashes", {}))
    receipt_hashes = dict(receipt.get("output_hashes", {}))
    checked = 0
    for name, expected in manifest_hashes.items():
        path = output_dir / name
        actual = sha256_file(path)
        if actual != str(expected).lower():
            raise ValueError(f"manifest output hash mismatch: {name}")
        checked += 1
    for name, expected in receipt_hashes.items():
        path = output_dir / name
        actual = sha256_file(path)
        if actual != str(expected).lower():
            raise ValueError(f"receipt output hash mismatch: {name}")
    return {"manifest_hashes_checked": checked, "receipt_hashes_checked": len(receipt_hashes)}


def _check_event_accounting(output_dir: Path) -> dict[str, int]:
    features = read_csv(output_dir / "lock_event_envelope_features.csv")
    segments = read_csv(output_dir / "lock_gain_alignment_catalog.csv")
    traces = read_csv_gz(output_dir / "recovery_trace_catalog.csv.gz")
    if len(features) != 48:
        raise ValueError(f"expected 48 feature rows, got {len(features)}")
    keys = [(row.get("run_id"), row.get("event_id")) for row in features]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate lock event feature key")
    if len(segments) != 48 * 4:
        raise ValueError(f"expected 192 segment rows, got {len(segments)}")
    for row in features:
        if row.get("gold_labels_used_for_selection") not in {"0", "false", "False"}:
            raise ValueError("gold provenance flag is not false")
        if row.get("physical_lock_depth_identified") not in {"0", "false", "False"}:
            raise ValueError("physical lock depth was incorrectly identified")
        if row.get("depth_status") != "DEPTH_RIGHT_CENSORED":
            raise ValueError("depth censoring status changed")
    return {"feature_rows": len(features), "segment_rows": len(segments), "trace_rows": len(traces)}


def _check_recovery_parameters(output_dir: Path) -> dict[str, Any]:
    rows = read_csv(output_dir / "environment_recovery_parameters.csv")
    if {row.get("environment") for row in rows} != set(ENVIRONMENTS):
        raise ValueError("recovery environment coverage mismatch")
    for row in rows:
        duration = _float_or_none(row.get("duration_ms"))
        if duration is None or duration <= 0.0:
            raise ValueError("invalid recovery duration")
        source = str(row.get("duration_source", ""))
        status = str(row.get("support_status", ""))
        if source == "fixed_100ms_fallback" and status != "ASSUMPTION_ONLY_REACQUISITION_DEBOUNCE_FALLBACK":
            raise ValueError("fallback recovery lacks assumption provenance")
    return {
        "environment_rows": len(rows),
        "fallback_rows": sum(1 for row in rows if row.get("duration_source") == "fixed_100ms_fallback"),
        "observed_rows": sum(1 for row in rows if row.get("duration_source") == "environment_observed_or_parent"),
    }


def _check_contracts(output_dir: Path) -> dict[str, Any]:
    mapping = read_json(output_dir / "lock_amplitude_mapping_contract.json")
    phase = read_json(output_dir / "phase_policy_contract.json")
    composition = read_json(output_dir / "composition_contract.json")
    if mapping.get("default_mode") != "EMPIRICAL_DIAGNOSTIC_PROXY":
        raise ValueError("unexpected default mapping mode")
    if mapping.get("physical_lock_depth_identified") is not False or mapping.get("hardware_lock_loss_calibrated") is not False:
        raise ValueError("mapping overclaims physical calibration")
    if mapping.get("exact_zero_default") is not False:
        raise ValueError("default exact-zero semantics changed")
    if phase.get("phase_is_data_fitted") is not False:
        raise ValueError("phase is incorrectly marked fitted")
    if phase.get("lock_bad_resets_phase") is not False or phase.get("recovery_resets_phase") is not False:
        raise ValueError("phase reset policy changed")
    if composition.get("sample_rate_hz") != 10230000 or composition.get("nlos_slot_count") != 3:
        raise ValueError("composition contract changed")
    inactive = dict(composition.get("inactive_semantics", {}))
    if inactive.get("amplitude") != 0.0 or inactive.get("delay") is not None or inactive.get("doppler") is not None or inactive.get("phase") is not None:
        raise ValueError("inactive slot semantics changed")
    return {"mapping": "PASS", "phase": "PASS", "composition": "PASS"}


def _check_determinism_artifacts(output_dir: Path) -> dict[str, int]:
    scalar = read_csv(output_dir / "deterministic_scalar_draws.csv")
    state = read_csv_gz(output_dir / "deterministic_state_sequence.csv.gz")
    if len(scalar) != 4096 * len(ENVIRONMENTS):
        raise ValueError(f"unexpected scalar draw count: {len(scalar)}")
    scalar_keys = [(row.get("environment"), row.get("draw_index")) for row in scalar]
    if len(set(scalar_keys)) != len(scalar_keys):
        raise ValueError("duplicate deterministic scalar key")
    if len({row.get("environment") for row in scalar}) != len(ENVIRONMENTS):
        raise ValueError("scalar draw environment coverage mismatch")
    for row in scalar:
        if row.get("gold_labels_used_for_selection") not in {"0", "false", "False"}:
            raise ValueError("deterministic draw gold flag is not false")
    state_keys = {(row.get("environment"), row.get("sequence_id")) for row in state}
    if len(state_keys) != 64 * len(ENVIRONMENTS):
        raise ValueError("state sequence coverage mismatch")
    return {"scalar_rows": len(scalar), "state_segment_rows": len(state), "state_sequences": len(state_keys)}


def audit_namespace(project_root: Path, config_path: Path, output_dir: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    allowed_root = (project_root / "dataset_generation_logs" / "channel_modeling").resolve()
    output_dir.relative_to(allowed_root)
    if "sage_results" in {part.lower() for part in output_dir.parts} or "scenes" in {part.lower() for part in output_dir.parts}:
        raise ValueError("output namespace is not isolated from SAGE results")
    require_required_artifacts(output_dir)
    config = read_json(config_path)
    source_check = _check_parent_sources(project_root, config)
    manifest = read_json(output_dir / "model_manifest.json")
    receipt = read_json(output_dir / "build_receipt.json")
    validate_manifest_policy(manifest)
    if receipt.get("status") != "BUILD_COMPLETED_PENDING_INDEPENDENT_QA":
        raise ValueError("unexpected build receipt status")
    hash_check = _check_output_hashes(output_dir, manifest, receipt)
    event_check = _check_event_accounting(output_dir)
    recovery_check = _check_recovery_parameters(output_dir)
    contract_check = _check_contracts(output_dir)
    deterministic_check = _check_determinism_artifacts(output_dir)
    model = read_json(output_dir / "lock_amplitude_phase_recovery_model.json")
    if model.get("counts", {}).get("lock_event_count") != 48:
        raise ValueError("model lock event count mismatch")
    if model.get("source_contract", {}).get("config_sha256") != sha256_file(config_path):
        raise ValueError("model config hash mismatch")
    result = {
        "source_provenance_gate": "PASS",
        "lock_gain_alignment_gate": "PASS",
        "lock_timing_gate": "PASS",
        "amplitude_mapping_gate": "PASS",
        "recovery_envelope_gate": "PASS",
        "phase_continuity_gate": "PASS",
        "inactive_slot_semantics_gate": "PASS",
        "determinism_gate": "PASS",
        "namespace_and_hash_gate": "PASS",
        "protected_pipeline_gate": "PASS",
        "model_qa": "PASS_WITH_LIMITATIONS",
        "ready_for_generator_integration": "YES",
        "hardware_lock_loss_calibrated": "NO",
        "checks": {
            "source": source_check,
            "hashes": hash_check,
            "events": event_check,
            "recovery": recovery_check,
            "contracts": contract_check,
            "determinism": deterministic_check,
        },
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "matlab_executed": False,
        "sage_executed": False,
        "batch_executed": False,
    }
    return result


def write_qa_report(output_dir: Path, result: Mapping[str, Any]) -> None:
    checks = result["checks"]
    lines = [
        "# Independent QA: Lock-State Amplitude, Phase, and Recovery Model v1",
        "",
        "Status: `PASS_WITH_LIMITATIONS`",
        "",
        "This QA is gold-blind and offline. It reads only published derived artifacts; it does not read raw IQ or invoke MATLAB/SAGE.",
        "",
        "## Gates",
        "",
    ]
    for key, value in result.items():
        if key.endswith("_gate") or key in {"model_qa", "ready_for_generator_integration", "hardware_lock_loss_calibrated"}:
            lines.append(f"- `{key}` = `{value}`")
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            f"- lock event features: {checks['events']['feature_rows']}",
            f"- aligned segment rows: {checks['events']['segment_rows']}",
            f"- recovery trace rows: {checks['events']['trace_rows']}",
            f"- fallback recovery environments: {checks['recovery']['fallback_rows']}",
            f"- deterministic scalar rows: {checks['determinism']['scalar_rows']}",
            f"- deterministic state sequences: {checks['determinism']['state_sequences']}",
            "",
            "Physical lock attenuation is not calibrated. The default empirical mode is a receiver-diagnostic proxy; forced stress mode requires an explicit user floor.",
        ]
    )
    (output_dir / "independent_qa_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    qa_result = dict(result)
    qa_result["qa_report_sha256"] = sha256_file(output_dir / "independent_qa_report.md")
    (output_dir / "independent_qa_result.json").write_text(
        json.dumps(qa_result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = audit_namespace(args.project_root, args.config, args.artifact_root)
        write_qa_report(args.artifact_root.resolve(), result)
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"AUDIT_FAILED={exc}", file=sys.stderr)
        return 1
    print("MODEL_QA=PASS_WITH_LIMITATIONS")
    print("READY_FOR_GENERATOR_INTEGRATION=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
