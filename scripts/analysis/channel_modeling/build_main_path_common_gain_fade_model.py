"""Build the versioned common-gain/observable-fade model from tracking only.

This builder does not open raw IQ and does not invoke MATLAB, GNSS-SDR, SAGE,
or any production entry point.  It writes only the requested new channel-model
namespace and fails closed if that namespace already exists.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import contextlib
import io
import platform
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import stats

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .main_path_gain_core import (
        ENVIRONMENTS,
        ELEVATION_BANDS,
        EXPECTED_SAMPLE_RATE_HZ,
        FadeEvent,
        GainFadeConfig,
        GainGridRow,
        GainRunInput,
        TrackingObservation,
        build_analysis_grid,
        compute_run_reference,
        compute_local_upper_baseline,
        db_to_linear_amplitude,
        extract_fade_events,
        fit_family,
        fit_latent_correlation_time,
        join_nearest_geometry,
        json_safe,
        read_csv_rows,
        read_tracking_observation,
        resolve_gain_model_runs,
        select_family_by_scene,
        sha256_file,
        tracking_sample_to_utc,
        utc_now,
    )
except ImportError:
    from scripts.analysis.channel_modeling.main_path_gain_core import (
        ENVIRONMENTS,
        ELEVATION_BANDS,
        EXPECTED_SAMPLE_RATE_HZ,
        FadeEvent,
        GainFadeConfig,
        GainGridRow,
        GainRunInput,
        TrackingObservation,
        build_analysis_grid,
        compute_run_reference,
        compute_local_upper_baseline,
        db_to_linear_amplitude,
        extract_fade_events,
        fit_family,
        fit_latent_correlation_time,
        join_nearest_geometry,
        json_safe,
        read_csv_rows,
        read_tracking_observation,
        resolve_gain_model_runs,
        select_family_by_scene,
        sha256_file,
        tracking_sample_to_utc,
        utc_now,
    )


MODEL_FILES = (
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
)


def validate_config_contract(config: GainFadeConfig) -> None:
    if config.sample_rate_hz != EXPECTED_SAMPLE_RATE_HZ:
        raise ValueError("sample rate must remain 10230000 Hz")
    if config.environments != ENVIRONMENTS or config.elevation_bands != ELEVATION_BANDS:
        raise ValueError("environment/elevation order is not frozen")
    if config.analysis_bin_ms != 20:
        raise ValueError("analysis grid must remain 20 ms")
    if config.entry_depth_db != 3.0 or config.entry_sustain_ms != 20:
        raise ValueError("fade entry rule changed")
    if config.exit_depth_db != 1.0 or config.exit_sustain_ms != 100:
        raise ValueError("fade exit rule changed")
    if config.geometry_tolerance_s != 5.0:
        raise ValueError("geometry tolerance changed")
    required_false = ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz")
    for key in required_false:
        if config.execution_policy.get(key) is not False:
            raise ValueError(f"execution policy {key} must be false")
    for key in ("gold_labels_used_for_selection", "stage3_stage4_used_for_selection"):
        if config.execution_policy.get(key) is not False:
            raise ValueError(f"gold leakage policy {key} must be false")
    if config.execution_policy.get("new_only") is not True or config.execution_policy.get("resume_allowed") is not False:
        raise ValueError("model output must be new_only and non-resumable")
    if not config.output_namespace.startswith("dataset_generation_logs/channel_modeling/"):
        raise ValueError("output namespace is outside channel_modeling")


def ensure_new_only_namespace(project_root: Path, output_dir: Path) -> None:
    root = (project_root / "dataset_generation_logs" / "channel_modeling").resolve()
    target = output_dir.resolve()
    if target.exists():
        raise FileExistsError(f"new-only output namespace already exists: {target}")
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"output namespace outside channel_modeling: {target}") from exc
    if target == root:
        raise ValueError("channel_modeling root cannot be used as output namespace")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})


def _append_csv(path: Path, row: Mapping[str, Any], fieldnames: Sequence[str], *, first: bool) -> None:
    mode = "w" if first else "a"
    with path.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        if first:
            writer.writeheader()
        writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})


def _parse_utc_seconds(value: str) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _load_geometry(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size <= 0:
        return []
    result: list[dict[str, Any]] = []
    for row in read_csv_rows(path):
        timestamp = _parse_utc_seconds(row.get("utc_time", ""))
        if timestamp is None:
            continue
        result.append(
            {
                "prn": row.get("prn", ""),
                "utc_seconds": timestamp,
                "utc_time": row.get("utc_time", ""),
                "elevation_deg": row.get("elevation_deg"),
                "azimuth_deg": row.get("azimuth_deg"),
                "snr_db_hz": row.get("snr_db_hz"),
            }
        )
    return result


def _attach_geometry(
    rows: Sequence[GainGridRow],
    run: GainRunInput,
    config: GainFadeConfig,
) -> tuple[list[dict[str, Any]], int, int]:
    records = _load_geometry(run.geometry_path) if run.geometry_path else []
    join_rows: list[dict[str, Any]] = []
    valid_count = 0
    invalid_count = 0
    for row in rows:
        if run.time_origin_utc is None:
            joined = None
        else:
            utc = tracking_sample_to_utc(row.time_s * config.sample_rate_hz, config.sample_rate_hz, run.time_origin_utc)
            joined = join_nearest_geometry(records, run.prn, utc.timestamp(), tolerance_s=config.geometry_tolerance_s)
        if joined is not None and joined.valid:
            row.elevation_deg = joined.elevation_deg
            row.elevation_band = None if joined.elevation_deg is None else _band_or_none(joined.elevation_deg)
            row.geometry_join_valid = True
            row.geometry_join_status = joined.status
            row.geometry_time_delta_s = joined.delta_s
            valid_count += 1
        else:
            reason = "time_origin_unavailable" if run.time_origin_utc is None else (joined.reason if joined else "geometry_unavailable")
            row.elevation_deg = None
            row.elevation_band = None
            row.geometry_join_valid = False
            row.geometry_join_status = reason or "unavailable"
            row.geometry_time_delta_s = None if joined is None else joined.delta_s
            invalid_count += 1
        join_rows.append(
            {
                "run_id": run.run_id,
                "scene_id": run.scene_id,
                "prn": run.prn,
                "tracking_channel": run.tracking_channel,
                "geometry_path": str(run.geometry_path) if run.geometry_path else "",
                "joined_rows": len(rows),
                "valid_rows": valid_count,
                "invalid_rows": invalid_count,
            }
        )
    return join_rows, valid_count, invalid_count


def _band_or_none(elevation: float) -> str | None:
    if not 0 <= elevation <= 90:
        return None
    if elevation < 30:
        return "LOW"
    if elevation < 60:
        return "MID"
    return "HIGH"


def _row_dict(row: GainGridRow, fade_event_id: str | None = None) -> dict[str, Any]:
    return {
        "run_id": row.run_id,
        "scene_id": row.scene_id,
        "prn": row.prn,
        "tracking_channel": row.tracking_channel,
        "environment": row.environment,
        "time_s": row.time_s,
        "time_bin_index": row.time_bin_index,
        "cn0_db_hz": row.cn0_db_hz,
        "c_ref_run_db_hz": row.c_ref_run_db_hz,
        "common_gain_db": row.common_gain_db,
        "common_gain_linear": row.common_gain_linear,
        "local_upper_db_hz": row.local_upper_db_hz,
        "fade_depth_db": row.fade_depth_db,
        "lock_state": row.lock_state,
        "continuity_valid": int(row.continuity_valid),
        "elevation_deg": row.elevation_deg,
        "elevation_band": row.elevation_band,
        "geometry_join_valid": int(row.geometry_join_valid),
        "geometry_join_status": row.geometry_join_status,
        "geometry_time_delta_s": row.geometry_time_delta_s,
        "baseline_status": row.baseline_status,
        "fade_event_id": fade_event_id,
    }


def _event_dict(event: FadeEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "scene_id": event.scene_id,
        "environment": event.environment,
        "elevation_band": event.elevation_band,
        "start_time_s": event.start_time_s,
        "end_time_s": event.end_time_s,
        "duration_s": event.duration_s,
        "max_observed_depth_db": event.max_observed_depth_db,
        "right_censored": int(event.right_censored),
        "censor_reason": event.censor_reason,
        "missing_depth_count": event.missing_depth_count,
        "elevation_cell_eligible": int(event.elevation_cell_eligible),
    }


def _fit_hierarchy(
    records: Sequence[Mapping[str, Any]],
    *,
    value_key: str,
    selected_family: str,
    positive: bool = False,
    censored_key: str | None = None,
) -> list[dict[str, Any]]:
    def prior_fit(family: str) -> Any:
        if family == "student_t":
            parameters = {"df": 10.0, "loc": 0.0, "scale": 1.0}
        elif family == "normal":
            parameters = {"loc": 0.0, "scale": 1.0}
        elif family == "laplace":
            parameters = {"loc": 0.0, "scale": 1.0}
        elif family in {"lognormal", "gamma", "weibull"}:
            parameters = {"shape": 1.0, "loc": 0.0, "scale": 1.0}
        else:
            raise ValueError(f"unknown family for prior: {family}")
        return type("PriorFit", (), {
            "family": family,
            "parameters": parameters,
            "log_likelihood": None,
            "converged": False,
        })()

    def fit_balanced(rows: Sequence[Mapping[str, Any]], family: str, censored: Sequence[bool] | None = None) -> Any:
        values = [float(row[value_key]) for row in rows]
        if not values:
            return prior_fit(family)
        from scripts.analysis.channel_modeling.main_path_gain_core import _scene_balanced_weights

        return fit_family(values, family, right_censored=censored, weights=_scene_balanced_weights(rows))

    def valid(group: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        result = []
        for row in group:
            value = row.get(value_key)
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(number) or (positive and number <= 0):
                continue
            result.append(row)
        return result

    all_rows = valid(records)
    global_fit = fit_balanced(
        all_rows,
        selected_family,
        [bool(row.get(censored_key, False)) for row in all_rows] if censored_key else None,
    )
    fits: list[dict[str, Any]] = [{
        "level": "global",
        "environment": "",
        "elevation_band": "",
        "family": global_fit.family,
        "parameters": json.dumps(json_safe(global_fit.parameters), sort_keys=True),
        "log_likelihood": global_fit.log_likelihood,
        "converged": int(global_fit.converged),
        "direct_count": len(all_rows),
        "parameter_source": "global_direct" if all_rows else "global_prior_only",
    }]
    env_fit: dict[str, Any] = {}
    for environment in ENVIRONMENTS:
        rows = valid(row for row in all_rows if row.get("environment") == environment)
        if rows:
            fit = fit_balanced(
                rows,
                selected_family,
                [bool(row.get(censored_key, False)) for row in rows] if censored_key else None,
            )
            source = "environment_direct"
        else:
            fit = global_fit
            source = "global_parent_only"
        env_fit[environment] = fit
        fits.append({
            "level": "environment",
            "environment": environment,
            "elevation_band": "",
            "family": fit.family,
            "parameters": json.dumps(json_safe(fit.parameters), sort_keys=True),
            "log_likelihood": fit.log_likelihood,
            "converged": int(fit.converged),
            "direct_count": len(rows),
            "parameter_source": source,
        })
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            rows = valid(
                row for row in all_rows
                if row.get("environment") == environment
                and row.get("elevation_band") == band
                and bool(row.get("geometry_join_valid"))
            )
            if rows:
                fit = fit_balanced(
                    rows,
                    selected_family,
                    [bool(row.get(censored_key, False)) for row in rows] if censored_key else None,
                )
                source = "cell_direct"
            else:
                fit = env_fit[environment]
                source = "environment_parent_only"
            fits.append({
                "level": "cell",
                "environment": environment,
                "elevation_band": band,
                "family": fit.family,
                "parameters": json.dumps(json_safe(fit.parameters), sort_keys=True),
                "log_likelihood": fit.log_likelihood,
                "converged": int(fit.converged),
                "direct_count": len(rows),
                "parameter_source": source,
            })
    return fits


def _fit_rates(grid_rows: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]], config: GainFadeConfig) -> list[dict[str, Any]]:
    def exposure(rows: Iterable[Mapping[str, Any]], *, cell: bool = False, environment: str = "", band: str = "") -> float:
        total = 0.0
        for row in rows:
            if row.get("lock_state") != "LOCK_GOOD" or not row.get("continuity_valid"):
                continue
            if row.get("fade_depth_db") is not None and float(row["fade_depth_db"]) >= config.entry_depth_db:
                continue
            if row.get("environment") != environment and environment:
                continue
            if cell and (not row.get("geometry_join_valid") or row.get("elevation_band") != band):
                continue
            total += config.analysis_bin_ms / 1000.0
        return total

    all_exposure = exposure(grid_rows)
    all_count = len(events)
    global_rate = (all_count + 1.0) / (all_exposure + 1.0)
    output: list[dict[str, Any]] = []
    for level, environment, band in [("global", "", "")]:
        output.append({
            "level": level, "environment": environment, "elevation_band": band,
            "direct_event_count": all_count, "exposure_s": all_exposure,
            "posterior_shape": all_count + 1.0, "posterior_rate_s": all_exposure + 1.0,
            "posterior_mean_rate_per_s": global_rate, "parameter_source": "global_direct",
        })
    env_rates: dict[str, float] = {}
    env_exposure: dict[str, float] = {}
    for environment in ENVIRONMENTS:
        exp = exposure(grid_rows, environment=environment)
        count = sum(1 for event in events if event.get("environment") == environment)
        prior_shape = max(global_rate * config.rate_parent_exposure_s, 1e-6)
        shape = prior_shape + count
        rate = config.rate_parent_exposure_s + exp
        mean = shape / rate
        env_rates[environment] = mean
        env_exposure[environment] = exp
        output.append({
            "level": "environment", "environment": environment, "elevation_band": "",
            "direct_event_count": count, "exposure_s": exp,
            "posterior_shape": shape, "posterior_rate_s": rate,
            "posterior_mean_rate_per_s": mean,
            "parameter_source": "environment_direct" if exp > 0 else "global_parent_only",
        })
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            exp = exposure(grid_rows, cell=True, environment=environment, band=band)
            count = sum(1 for event in events if event.get("environment") == environment and event.get("elevation_band") == band and event.get("elevation_cell_eligible"))
            parent_rate = env_rates[environment]
            prior_shape = max(parent_rate * config.rate_parent_exposure_s, 1e-6)
            shape = prior_shape + count
            rate = config.rate_parent_exposure_s + exp
            if exp <= 0:
                mean = parent_rate
                source = "environment_parent_only"
            else:
                mean = shape / rate
                source = "cell_direct"
            output.append({
                "level": "cell", "environment": environment, "elevation_band": band,
                "direct_event_count": count, "exposure_s": exp,
                "posterior_shape": shape, "posterior_rate_s": rate,
                "posterior_mean_rate_per_s": mean,
                "parameter_source": source,
            })
    return output


def _fit_family_selection(grid_rows: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]], config: GainFadeConfig) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normal = [row for row in grid_rows if row.get("common_gain_db") is not None and row.get("lock_state") == "LOCK_GOOD" and row.get("continuity_valid") and (row.get("fade_depth_db") is None or float(row.get("fade_depth_db")) < config.entry_depth_db)]
    fade_depth = [row for row in events if row.get("max_observed_depth_db") is not None]
    fade_duration = [row for row in events if float(row.get("duration_s", 0.0)) > 0]
    cases = [
        ("normal_gain_db", normal, config.marginal_families["normal_gain_db"], False),
        ("fade_depth_db", fade_depth, config.marginal_families["fade_depth_db"], True),
        ("fade_duration_s", fade_duration, config.marginal_families["fade_duration_s"], True),
    ]
    selection_rows: list[dict[str, Any]] = []
    selected: dict[str, Any] = {}
    for name, records, families, positive in cases:
        value_key = "common_gain_db" if name == "normal_gain_db" else ("max_observed_depth_db" if name == "fade_depth_db" else "duration_s")
        if not records:
            selected[name] = {"selected_family": families[0], "scores": {}, "status": "PRIOR_ONLY_NO_EVENTS"}
            selection_rows.append({"parameter": name, "selected_family": families[0], "scores": "{}", "held_out_groups": "", "row_random_split_used": 0, "status": "PRIOR_ONLY_NO_EVENTS"})
            continue
        exact = [record for record in records if not bool(record.get("right_censored", False))]
        fit_records = exact if positive and exact else records
        if positive and not any(float(record.get(value_key, 0.0)) > 0 for record in fit_records):
            selected[name] = {"selected_family": families[0], "scores": {}, "status": "INCONCLUSIVE"}
            continue
        try:
            selection = select_family_by_scene(
                [{"scene_id": row.get("scene_id", ""), value_key: row.get(value_key)} for row in fit_records],
                value_key,
                families,
            )
            selected[name] = {"selected_family": selection.selected_family, "scores": dict(selection.scores), "status": "SELECTED"}
            selection_rows.append({
                "parameter": name,
                "selected_family": selection.selected_family,
                "scores": json.dumps(json_safe(selection.scores), sort_keys=True),
                "held_out_groups": ";".join(selection.held_out_groups),
                "row_random_split_used": int(selection.row_random_split_used),
                "status": "SELECTED",
            })
        except ValueError:
            selected[name] = {"selected_family": families[0], "scores": {}, "status": "INCONCLUSIVE"}
            selection_rows.append({"parameter": name, "selected_family": families[0], "scores": "{}", "held_out_groups": "", "row_random_split_used": 0, "status": "INCONCLUSIVE"})
    return selected, selection_rows


def _normal_gain_records(
    grid_rows: Sequence[Mapping[str, Any]],
    config: GainFadeConfig,
) -> list[Mapping[str, Any]]:
    """Return only valid non-fade rows for the normal-state gain fit."""

    result: list[Mapping[str, Any]] = []
    for row in grid_rows:
        value = row.get("common_gain_db")
        if value in (None, "") or row.get("lock_state") != "LOCK_GOOD" or not row.get("continuity_valid"):
            continue
        if row.get("fade_depth_db") not in (None, "") and float(row["fade_depth_db"]) >= config.entry_depth_db:
            continue
        result.append(row)
    return result


def _qa_draws(model: Mapping[str, Any], config: GainFadeConfig) -> list[dict[str, Any]]:
    rng = np.random.default_rng(config.qa_draw_seed)
    result: list[dict[str, Any]] = []
    for cell, info in sorted(model["gain_marginals"]["cells"].items()):
        family = str(info.get("family", "normal"))
        parameters = info["parameters"]
        if family == "student_t":
            values = stats.t.rvs(
                df=float(parameters.get("df", 10.0)),
                loc=float(parameters.get("loc", 0.0)),
                scale=max(float(parameters.get("scale", 1.0)), 1e-9),
                size=config.qa_draw_count,
                random_state=rng,
            )
        elif family == "laplace":
            values = stats.laplace.rvs(
                loc=float(parameters.get("loc", 0.0)),
                scale=max(float(parameters.get("scale", 1.0)), 1e-9),
                size=config.qa_draw_count,
                random_state=rng,
            )
        else:
            values = stats.norm.rvs(
                loc=float(parameters.get("loc", 0.0)),
                scale=max(float(parameters.get("scale", 1.0)), 1e-9),
                size=config.qa_draw_count,
                random_state=rng,
            )
        result.append({
            "cell": cell,
            "draw_count": config.qa_draw_count,
            "seed": config.qa_draw_seed,
            "gain_p10_db": float(np.quantile(values, 0.1)),
            "gain_p50_db": float(np.quantile(values, 0.5)),
            "gain_p90_db": float(np.quantile(values, 0.9)),
            "gain_min_db": float(np.min(values)),
            "gain_max_db": float(np.max(values)),
            "finite": int(np.all(np.isfinite(values))),
        })
    return result


def _fit_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "family": row["family"],
        "parameters": json.loads(str(row["parameters"])),
        "direct_count": int(row["direct_count"]),
        "parameter_source": row["parameter_source"],
    }


def freeze_model_manifest(
    config: GainFadeConfig,
    *,
    config_hash: str,
    source_preflight_hash: str,
    code_hashes: Mapping[str, str],
    output_hashes: Mapping[str, str],
    output_namespace: str | None = None,
) -> dict[str, Any]:
    return {
        "model_id": config.model_id,
        "model_version": config.model_version,
        "output_namespace": output_namespace or config.output_namespace,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "config_sha256": config_hash,
        "source_preflight_sha256": source_preflight_hash,
        "source_contract": json_safe(config.source),
        "protected_source": json_safe(config.protected_source),
        "code_hashes": dict(code_hashes),
        "output_hashes": dict(output_hashes),
        "sample_rate_hz": config.sample_rate_hz,
        "analysis_grid": {
            "bin_ms": config.analysis_bin_ms,
            "baseline_window_s": config.baseline_window_s,
            "baseline_quantile": config.baseline_quantile,
        },
        "fade_rule": {
            "entry_depth_db": config.entry_depth_db,
            "entry_sustain_ms": config.entry_sustain_ms,
            "exit_depth_db": config.exit_depth_db,
            "exit_sustain_ms": config.exit_sustain_ms,
        },
        "geometry": {
            "maximum_nearest_delta_s": config.geometry_tolerance_s,
            "interpolation": False,
            "same_prn_required": True,
        },
        "execution_policy": json_safe(config.execution_policy),
        "environment": {
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "numpy_version": np.__version__,
            "scipy_version": __import__("scipy").__version__,
        },
        "scientific_semantics": {
            "common_gain_is": "run-normalized tracking CN0 proxy",
            "absolute_rf_power": False,
            "path_zero_is_physical_los": False,
            "lock_bad_depth": "right_censored_not_exact",
            "gold_labels_used_for_selection": False,
        },
    }


def build_model(project_root: Path, config_path: Path, output_dir: Path) -> dict[str, Any]:
    start = utc_now()
    config = GainFadeConfig.from_json(config_path)
    validate_config_contract(config)
    ensure_new_only_namespace(project_root, output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        source_preflight: list[dict[str, Any]] = []
        for key, value in config.source.items():
            path = project_root / Path(str(value)) if key.endswith("relative_path") else None
            if path is None:
                continue
            expected_key = key.replace("relative_path", "sha256")
            expected_hash = str(config.source.get(expected_key, ""))
            actual_hash = sha256_file(path) if path.is_file() else ""
            if not path.is_file() or actual_hash.lower() != expected_hash.lower():
                raise ValueError(f"source preflight failed for {key}: {path}")
            source_preflight.append({"source_key": key, "path": str(path), "sha256": actual_hash, "status": "PASS"})
        runs = resolve_gain_model_runs(project_root, config)
        if len(runs) != 63:
            raise ValueError(f"expected 63 eligible runs, resolved {len(runs)}")
        unique_physical = {(run.tracking_sha256, run.prn, run.tracking_channel) for run in runs}
        for run in runs:
            source_preflight.append({
                "source_key": f"tracking:{run.run_id}",
                "path": str(run.tracking_path),
                "sha256": run.tracking_sha256,
                "size_bytes": run.tracking_path.stat().st_size,
                "scene_id": run.scene_id,
                "prn": run.prn,
                "tracking_channel": run.tracking_channel,
                "environment": run.environment,
                "duplicate_physical_input": int(sum(1 for item in runs if (item.tracking_sha256, item.prn, item.tracking_channel) == (run.tracking_sha256, run.prn, run.tracking_channel)) > 1),
                "status": "PASS",
            })
        _write_csv(output_dir / "source_preflight.csv", source_preflight, ["source_key", "path", "sha256", "size_bytes", "scene_id", "prn", "tracking_channel", "environment", "duplicate_physical_input", "status"])
        source_hash = sha256_file(output_dir / "source_preflight.csv")

        all_rows: list[GainGridRow] = []
        all_events: list[FadeEvent] = []
        geometry_rows: list[dict[str, Any]] = []
        run_summaries: list[dict[str, Any]] = []
        fade_event_ids_by_run: dict[str, list[FadeEvent]] = defaultdict(list)
        for run in runs:
            observation = read_tracking_observation(run, sample_rate_hz=config.sample_rate_hz)
            rows = build_analysis_grid(observation, bin_ms=config.analysis_bin_ms)
            _, valid_geometry, invalid_geometry = _attach_geometry(rows, run, config)
            compute_local_upper_baseline(
                rows,
                window_s=config.baseline_window_s,
                quantile=config.baseline_quantile,
                short_segment_min_duration_s=config.short_segment_min_duration_s,
                minimum_points=config.minimum_baseline_points,
            )
            result = extract_fade_events(rows, config)
            all_events.extend(result.events)
            fade_event_ids_by_run[run.run_id].extend(result.events)
            all_rows.extend(rows)
            geometry_rows.append({
                "run_id": run.run_id,
                "scene_id": run.scene_id,
                "prn": run.prn,
                "tracking_channel": run.tracking_channel,
                "geometry_path": str(run.geometry_path) if run.geometry_path else "",
                "grid_rows": len(rows),
                "valid_geometry_rows": valid_geometry,
                "invalid_geometry_rows": invalid_geometry,
                "geometry_coverage_fraction": valid_geometry / len(rows) if rows else 0.0,
                "time_origin_available": int(run.time_origin_utc is not None),
            })
            run_summaries.append({
                "run_id": run.run_id,
                "scene_id": run.scene_id,
                "prn": run.prn,
                "tracking_channel": run.tracking_channel,
                "environment": run.environment,
                "tracking_path": str(run.tracking_path),
                "tracking_sha256": run.tracking_sha256,
                "tracking_records": int(observation.times_s.size),
                "valid_tracking_records": observation.valid_count,
                "inconclusive_tracking_records": observation.inconclusive_count,
                "analysis_grid_rows": len(rows),
                "fade_event_count": len(result.events),
                "fade_missing_rows": result.missing_rows,
                "median_interval_s": observation.median_interval_s,
                "gap_limit_s": observation.gap_limit_s,
                "run_reference_cn0_db_hz": compute_run_reference(observation),
            })

        for row in all_rows:
            event_id = ""
            for event in fade_event_ids_by_run.get(row.run_id, []):
                if event.start_time_s <= row.time_s <= event.end_time_s:
                    event_id = event.event_id
                    break
            row_dict = _row_dict(row, event_id or None)
            row._export_dict = row_dict  # type: ignore[attr-defined]
        _write_csv(output_dir / "geometry_join_coverage.csv", geometry_rows, list(geometry_rows[0]) if geometry_rows else ["run_id"])
        _write_csv(output_dir / "common_gain_run_summary.csv", run_summaries, list(run_summaries[0]) if run_summaries else ["run_id"])
        _write_csv(output_dir / "fade_event_catalog.csv", [_event_dict(event) for event in all_events], [
            "event_id", "run_id", "scene_id", "environment", "elevation_band", "start_time_s", "end_time_s", "duration_s", "max_observed_depth_db", "right_censored", "censor_reason", "missing_depth_count", "elevation_cell_eligible"
        ])
        grid_fields = list(_row_dict(all_rows[0]).keys()) if all_rows else ["run_id"]
        with gzip.open(output_dir / "common_gain_analysis_grid.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=grid_fields, extrasaction="ignore")
            writer.writeheader()
            for row in all_rows:
                event_id = ""
                for event in fade_event_ids_by_run.get(row.run_id, []):
                    if event.start_time_s <= row.time_s <= event.end_time_s:
                        event_id = event.event_id
                        break
                writer.writerow({key: "" if value is None else value for key, value in _row_dict(row, event_id or None).items()})

        grid_records = []
        for row in all_rows:
            event_id = ""
            for event in fade_event_ids_by_run.get(row.run_id, []):
                if event.start_time_s <= row.time_s <= event.end_time_s:
                    event_id = event.event_id
                    break
            grid_records.append(_row_dict(row, event_id or None))
        event_records = [_event_dict(event) for event in all_events]
        selected, selection_rows = _fit_family_selection(grid_records, event_records, config)
        _write_csv(output_dir / "family_selection.csv", selection_rows, ["parameter", "selected_family", "scores", "held_out_groups", "row_random_split_used", "status"])

        normal_family = selected["normal_gain_db"]["selected_family"]
        depth_family = selected["fade_depth_db"]["selected_family"]
        duration_family = selected["fade_duration_s"]["selected_family"]
        normal_records = _normal_gain_records(grid_records, config)
        gain_fits = _fit_hierarchy(normal_records, value_key="common_gain_db", selected_family=normal_family)
        depth_fits = _fit_hierarchy(event_records, value_key="max_observed_depth_db", selected_family=depth_family, positive=True, censored_key="right_censored")
        duration_fits = _fit_hierarchy(event_records, value_key="duration_s", selected_family=duration_family, positive=True, censored_key="right_censored")
        _write_csv(output_dir / "common_gain_marginal_parameters.csv", gain_fits, ["level", "environment", "elevation_band", "family", "parameters", "log_likelihood", "converged", "direct_count", "parameter_source"])
        _write_csv(output_dir / "fade_depth_duration_parameters.csv", [
            {**row, "parameter": "fade_depth_db"} for row in depth_fits
        ] + [
            {**row, "parameter": "fade_duration_s"} for row in duration_fits
        ], ["parameter", "level", "environment", "elevation_band", "family", "parameters", "log_likelihood", "converged", "direct_count", "parameter_source"])

        cells: dict[str, dict[str, Any]] = {}
        for row in gain_fits:
            if row["level"] == "cell":
                cells[f"{row['environment']}|{row['elevation_band']}"] = _fit_to_dict(row)
        # Exposure and event support are deliberately reported separately from
        # the marginal fit; a cell with no direct geometry is a parent model.
        cell_rows: list[dict[str, Any]] = []
        for environment in ENVIRONMENTS:
            for band in ELEVATION_BANDS:
                direct_rows = [row for row in grid_records if row.get("environment") == environment and row.get("elevation_band") == band and row.get("geometry_join_valid") and row.get("common_gain_db") is not None]
                direct_events = [event for event in event_records if event.get("environment") == environment and event.get("elevation_band") == band and event.get("elevation_cell_eligible")]
                cell_rows.append({
                    "environment": environment,
                    "elevation_band": band,
                    "gain_direct_rows": len(direct_rows),
                    "fade_direct_events": len(direct_events),
                    "geometry_ready_exposure_s": len(direct_rows) * config.analysis_bin_ms / 1000.0,
                    "gain_support_status": "DATA_SUPPORTED_WITH_GROUPED_VALIDATION" if len(direct_rows) >= 3000 else ("SPARSE_PARTIAL_POOLING" if direct_rows else "PRIOR_ONLY"),
                    "fade_support_status": "DATA_SUPPORTED_WITH_GROUPED_VALIDATION" if len(direct_events) >= 10 else ("SPARSE_PARTIAL_POOLING" if direct_events else "PRIOR_ONLY"),
                    "parameter_source": cells[f"{environment}|{band}"]["parameter_source"],
                })
        _write_csv(output_dir / "cell_coverage.csv", cell_rows, list(cell_rows[0]) if cell_rows else ["environment"])
        rates = _fit_rates(grid_records, event_records, config)
        _write_csv(output_dir / "fade_entry_rate_parameters.csv", rates, ["level", "environment", "elevation_band", "direct_event_count", "exposure_s", "posterior_shape", "posterior_rate_s", "posterior_mean_rate_per_s", "parameter_source"])

        temporal_rows: list[dict[str, Any]] = []
        for level, environment, band in [("global", "", "")] + [("environment", env, "") for env in ENVIRONMENTS] + [("cell", env, b) for env in ENVIRONMENTS for b in ELEVATION_BANDS]:
            subset = [row for row in all_rows if (not environment or row.environment == environment) and (not band or row.elevation_band == band)]
            fit = fit_latent_correlation_time(subset, lag_s=config.lag_s, tau_min_s=config.tau_min_s, tau_max_s=config.tau_max_s)
            source = "direct"
            if level == "cell" and fit.fit_status != "FITTED":
                source = "environment_parent_only"
            temporal_rows.append({"level": level, "environment": environment, "elevation_band": band, "tau_s": fit.tau_s, "pair_count": fit.pair_count, "cross_gap_pairs": fit.cross_gap_pairs, "fit_status": fit.fit_status, "parameter_source": source})
        _write_csv(output_dir / "common_gain_temporal_parameters.csv", temporal_rows, list(temporal_rows[0]) if temporal_rows else ["level"])

        gain_by_cell = {key: value for key, value in cells.items()}
        global_gain_row = next(row for row in gain_fits if row["level"] == "global")
        environment_gain_rows = {
            row["environment"]: _fit_to_dict(row)
            for row in gain_fits
            if row["level"] == "environment"
        }
        model = {
            "model_id": config.model_id,
            "model_version": config.model_version,
            "sample_rate_hz": config.sample_rate_hz,
            "units": {"gain_db": "dB relative to per-run median tracking C/N0", "gain_linear": "linear amplitude ratio", "fade_depth_db": "dB C/N0 proxy", "duration_s": "s"},
            "gain_marginals": {
                "normal_gain_family": normal_family,
                "global": _fit_to_dict(global_gain_row),
                "environments": environment_gain_rows,
                "cells": gain_by_cell,
            },
            "fade_marginals": {"depth_family": depth_family, "duration_family": duration_family},
            "composition_contract": {"path_zero_amplitude": "G_common_linear", "nlos_amplitude": "G_common_linear * relative_nlos_amplitude", "path_zero_is_physical_los": False},
            "phase_policy": "outside this model; external initial phase and Doppler-continuous evolution",
            "lock_policy": "outside this model; LOCK_BAD depth is censored",
            "gold_labels_used_for_selection": False,
        }
        (output_dir / "main_path_common_gain_fade_model.json").write_text(json.dumps(json_safe(model), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        _write_csv(output_dir / "qa_draw_summary.csv", _qa_draws(model, config), ["cell", "draw_count", "seed", "gain_p10_db", "gain_p50_db", "gain_p90_db", "gain_min_db", "gain_max_db", "finite"])

        code_paths = {
            "core": Path(__file__).with_name("main_path_gain_core.py"),
            "builder": Path(__file__),
            "config": config_path,
        }
        code_hashes = {key: sha256_file(path) for key, path in code_paths.items()}
        output_hashes = {name: sha256_file(output_dir / name) for name in MODEL_FILES if (output_dir / name).is_file()}
        config_hash = sha256_file(config_path)
        manifest = freeze_model_manifest(
            config,
            config_hash=config_hash,
            source_preflight_hash=source_hash,
            code_hashes=code_hashes,
            output_hashes=output_hashes,
            output_namespace=str(output_dir),
        )
        (output_dir / "model_manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        manifest_hash = sha256_file(output_dir / "model_manifest.json")
        output_files = sorted(name for name in MODEL_FILES + ("model_manifest.json",) if (output_dir / name).is_file())
        artifact_hashes = {name: sha256_file(output_dir / name) for name in output_files}
        receipt = {
            "status": "completed",
            "start_utc": start,
            "end_utc": utc_now(),
            "raw_iq_read": False,
            "matlab_executed": False,
            "sage_executed": False,
            "batch_executed": False,
            "gold_labels_used_for_selection": False,
            "eligible_run_count": len(runs),
            "unique_physical_tracking_inputs": len(unique_physical),
            "grid_row_count": len(all_rows),
            "fade_event_count": len(all_events),
            "output_namespace": str(output_dir),
            "model_manifest_sha256": manifest_hash,
            "output_files": output_files,
            "output_hashes": artifact_hashes,
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "scipy_version": __import__("scipy").__version__,
        }
        (output_dir / "run_receipt.json").write_text(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return receipt
    except Exception as exc:
        failure = {"status": "failed", "start_utc": start, "end_utc": utc_now(), "error": str(exc), "output_namespace": str(output_dir), "raw_iq_read": False, "matlab_executed": False, "sage_executed": False, "batch_executed": False}
        (output_dir / "run_receipt.json").write_text(json.dumps(json_safe(failure), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    build_model(args.project_root.resolve(), args.config.resolve(), args.output.resolve())
    print(f"MODEL_OUTPUT={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
