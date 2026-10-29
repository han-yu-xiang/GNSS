"""WP6 analysis primitives for the frozen Mainline Stage2 population.

The count model is conditional on a window having been selected by Stage2.
It is not a model of all Stage0 windows.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


FEATURES_SHA256 = "258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4"
MPC_SHA256 = "8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b"
EXPECTED_INPUT_HASHES = {"features": FEATURES_SHA256, "mpcs": MPC_SHA256}
WINDOW_KEY = ("run_id", "window_id")
MPC_KEY = ("run_id", "window_id", "path_id")
COUNT_SUPPORT = (0, 1, 2, 3)
DEFAULT_CONTRACT = {
    "window_n": 7847,
    "mpc_n": 8914,
    "scene_n": 13,
    "count_support": COUNT_SUPPORT,
}

WINDOW_REQUIRED = {
    "run_id", "window_id", "scene_id", "stage2_mpc_count",
    "pdp_peak_at_grid_boundary", "pdp_rms_width_code_delay_samples",
    "pdp_peak_minus_sage_direct_delay_samples",
}
MPC_REQUIRED = {
    "run_id", "window_id", "path_id", "scene_id", "is_multipath",
    "modeling_role", "excess_delay_chips", "doppler_offset_hz",
    "relative_power_db",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_pinned_csv(path, required_columns, expected_sha, label):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{label} input does not exist: {path}")
    actual_sha = _sha256(path)
    if expected_sha and actual_sha.lower() != str(expected_sha).lower():
        raise ValueError(f"{label} SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")
    frame = pd.read_csv(path, dtype={key: "string" for key in ("run_id", "window_id", "path_id", "scene_id")})
    missing = sorted(required_columns.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} schema missing required columns: {missing}")
    return frame, actual_sha


def load_wp6_inputs(features_path, mpc_path, expected_hashes=None, expected_contract=None):
    """Read the two frozen WP4 CSVs and bind their exact bytes and row counts."""
    hashes = EXPECTED_INPUT_HASHES if expected_hashes is None else dict(expected_hashes)
    if set(hashes) != {"features", "mpcs"}:
        raise ValueError("expected_hashes must contain exactly 'features' and 'mpcs'")
    windows, features_sha = _read_pinned_csv(
        features_path, WINDOW_REQUIRED, hashes["features"], "features")
    mpcs, mpc_sha = _read_pinned_csv(mpc_path, MPC_REQUIRED, hashes["mpcs"], "MPC")
    validate_wp6_population(windows, mpcs, expected_contract=expected_contract)
    manifest = {
        "features_path": str(Path(features_path).resolve()),
        "features_sha256": features_sha,
        "features_rows": int(len(windows)),
        "mpc_path": str(Path(mpc_path).resolve()),
        "mpc_sha256": mpc_sha,
        "mpc_rows": int(len(mpcs)),
        "window_key": list(WINDOW_KEY),
        "mpc_key": list(MPC_KEY),
        "population_scope": "Stage2-selected windows only; conditional on Stage2 selection",
    }
    return windows, mpcs, manifest


def _require_columns(frame, required, label):
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"{label} schema missing required columns: {missing}")


def _canonicalize_keys(frame, keys, label):
    frame = frame.copy()
    for key in keys:
        if frame[key].isna().any():
            raise ValueError(f"{label} contains missing {key}")
        values = frame[key].astype("string").str.strip()
        if values.eq("").any():
            raise ValueError(f"{label} contains empty {key}")
        frame[key] = values
    return frame


def _numeric(frame, column, label, allow_missing=False):
    values = pd.to_numeric(frame[column], errors="coerce").astype(float)
    if not allow_missing and (values.isna().any() or not np.isfinite(values.to_numpy()).all()):
        raise ValueError(f"{label}.{column} contains missing or non-finite values")
    return values


def validate_wp6_population(windows, mpcs, expected_contract=None):
    """Validate exact window/path identity and the selected-window denominator."""
    contract = dict(DEFAULT_CONTRACT if expected_contract is None else expected_contract)
    required = {
        "window_n", "mpc_n", "scene_n", "count_support"
    }
    if not required.issubset(contract):
        raise ValueError(f"expected_contract missing fields: {sorted(required - set(contract))}")
    _require_columns(windows, WINDOW_REQUIRED, "windows")
    _require_columns(mpcs, MPC_REQUIRED, "MPCs")
    windows = _canonicalize_keys(windows, (*WINDOW_KEY, "scene_id"), "windows")
    mpcs = _canonicalize_keys(mpcs, (*MPC_KEY, "scene_id"), "MPCs")

    if windows.duplicated(list(WINDOW_KEY)).any():
        raise ValueError("duplicate selected-window key")
    if mpcs.duplicated(list(MPC_KEY)).any():
        raise ValueError("duplicate MPC path key")

    window_counts = _numeric(windows, "stage2_mpc_count", "windows")
    rounded = np.rint(window_counts.to_numpy())
    if not np.array_equal(window_counts.to_numpy(), rounded):
        raise ValueError("stage2_mpc_count must contain integer counts")
    support = tuple(int(value) for value in contract["count_support"])
    if not set(rounded.astype(int)).issubset(set(support)):
        raise ValueError(f"window count outside declared support {support}")

    for column in ("excess_delay_chips", "doppler_offset_hz", "relative_power_db"):
        _numeric(mpcs, column, "MPCs")
    multipath = pd.to_numeric(mpcs["is_multipath"], errors="coerce")
    if multipath.isna().any() or not multipath.eq(1).all():
        raise ValueError("MPC input includes a row not identified as a multipath path")
    if not mpcs["modeling_role"].astype("string").eq("MPC_CANDIDATE").all():
        raise ValueError("MPC input includes a row outside MPC_CANDIDATE role")

    scene_by_run = windows.groupby("run_id", dropna=False)["scene_id"].nunique()
    if not scene_by_run.eq(1).all():
        raise ValueError("a run_id maps to more than one scene_id")
    window_scene = windows.set_index(list(WINDOW_KEY))["scene_id"]
    mpc_scene = mpcs.set_index(list(WINDOW_KEY))["scene_id"]
    extra_window_keys = mpc_scene.index.difference(window_scene.index)
    if len(extra_window_keys):
        raise ValueError(f"MPC paths reference unknown selected-window keys: {list(extra_window_keys[:3])}")
    joined_scene = mpc_scene.to_frame("mpc_scene").join(window_scene.rename("window_scene"), how="left")
    if not joined_scene["mpc_scene"].eq(joined_scene["window_scene"]).all():
        raise ValueError("MPC scene_id does not match its selected-window scene_id")

    observed = mpcs.groupby(list(WINDOW_KEY), dropna=False).size()
    declared = windows.set_index(list(WINDOW_KEY))["stage2_mpc_count"].astype(int)
    reconciled = observed.reindex(declared.index, fill_value=0)
    if not reconciled.astype(int).equals(declared):
        mismatch = declared[reconciled.astype(int).ne(declared)].head(3).to_dict()
        raise ValueError(f"selected-window MPC counts do not reconcile with path rows: {mismatch}")

    actual = {
        "window_n": int(len(windows)),
        "mpc_n": int(len(mpcs)),
        "scene_n": int(windows["scene_id"].nunique()),
        "count_support": tuple(sorted(set(rounded.astype(int)))),
    }
    for key in ("window_n", "mpc_n", "scene_n"):
        if actual[key] != int(contract[key]):
            raise ValueError(f"{key} mismatch: expected {contract[key]}, got {actual[key]}")
    if not set(actual["count_support"]).issubset(set(support)):
        raise ValueError(f"observed count support {actual['count_support']} exceeds {support}")
    return None


def _validate_count_frame(frame, label):
    _require_columns(frame, (*WINDOW_KEY, "scene_id", "stage2_mpc_count"), label)
    if frame.duplicated(list(WINDOW_KEY)).any():
        raise ValueError(f"{label} contains duplicate selected-window keys")
    counts = _numeric(frame, "stage2_mpc_count", label)
    if not np.array_equal(counts.to_numpy(), np.rint(counts.to_numpy())):
        raise ValueError(f"{label} contains noninteger count values")
    if not set(counts.astype(int)).issubset(set(COUNT_SUPPORT)):
        raise ValueError(f"{label} contains counts outside {COUNT_SUPPORT}")
    if frame["scene_id"].isna().any() or frame["scene_id"].astype("string").str.strip().eq("").any():
        raise ValueError(f"{label} contains missing scene_id")
    return counts.astype(int)


def fit_count_probabilities(training_windows):
    """Equal-scene macro empirical frequencies; no smoothing for absent bins."""
    counts = _validate_count_frame(training_windows, "training windows")
    if training_windows.empty:
        raise ValueError("cannot fit count probabilities with no training windows")
    work = training_windows[["scene_id"]].copy()
    work["count"] = counts.to_numpy()
    scene_probabilities = []
    for _, scene in work.groupby("scene_id", sort=True, dropna=False):
        frequencies = scene["count"].value_counts(normalize=True)
        scene_probabilities.append({category: float(frequencies.get(category, 0.0))
                                    for category in COUNT_SUPPORT})
    scene_n = len(scene_probabilities)
    return {
        category: float(sum(scene[category] for scene in scene_probabilities) / scene_n)
        for category in COUNT_SUPPORT
    }


def score_count_fold(training_windows, test_windows):
    """Score a held-out scene set without smoothing unseen training categories."""
    train_counts = _validate_count_frame(training_windows, "training windows")
    test_counts = _validate_count_frame(test_windows, "test windows")
    train_scenes = set(training_windows["scene_id"].astype("string"))
    test_scenes = set(test_windows["scene_id"].astype("string"))
    overlap = train_scenes.intersection(test_scenes)
    if overlap:
        raise ValueError(f"training/test scene leakage: {sorted(overlap)}")
    probabilities = fit_count_probabilities(training_windows)
    rows = test_windows[list(WINDOW_KEY + ("scene_id",))].copy().reset_index(drop=True)
    observed = test_counts.to_numpy()
    row_probabilities = np.asarray([probabilities[int(count)] for count in observed], dtype=float)
    rows["stage2_mpc_count"] = observed
    rows["predicted_probability"] = row_probabilities
    supported = row_probabilities > 0.0
    rows["status"] = np.where(supported, "SCORED", "UNSUPPORTED_COUNT_CATEGORY")
    rows["log_score"] = np.where(supported, np.log(np.maximum(row_probabilities, np.finfo(float).tiny)), np.nan)
    scene_rows = []
    for scene_id, scene in rows.groupby("scene_id", sort=True, dropna=False):
        is_supported = scene["status"].eq("SCORED").all()
        scene_rows.append({
            "scene_id": scene_id,
            "window_n": int(len(scene)),
            "unsupported_window_n": int(scene["status"].ne("SCORED").sum()),
            "status": "SCORED" if is_supported else "UNSUPPORTED_COUNT_CATEGORY",
            "mean_log_score": float(scene["log_score"].mean()) if is_supported else np.nan,
        })
    return probabilities, rows, pd.DataFrame(scene_rows)
