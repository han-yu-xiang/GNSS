"""Support-gated environment/geometry models for the selected Stage2 MPC population.

This module consumes only the small, frozen CSV extracts produced by the
accepted Mainline Stage2 V0 audit. It never opens SAGE/CIR payloads.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from scipy import optimize, stats


CORE_ENVIRONMENTS = ("Urban", "Mountain/Valley")
SUPPLEMENT_ENVIRONMENTS = ("Highway/Open", "Special Reflective")
ENVIRONMENT_ORDER = CORE_ENVIRONMENTS + SUPPLEMENT_ENVIRONMENTS
MPC_KEY = ("run_id", "window_id", "path_id")
WINDOW_KEY = ("run_id", "window_id")
IDENTITY_TAGS = ("scene_id", "environment_class", "prn", "tracking_channel")
VARIABLE_FAMILIES = {
    "excess_delay_chips": ("gamma", "lognormal", "weibull"),
    "doppler_offset_hz": ("normal", "laplace", "student_t"),
    "relative_power_db": ("normal", "laplace", "student_t"),
}
ANGLE_SOURCES = (
    ("GSV_MEASURED", ""),
    ("EPHEMERIS_DERIVED", "GGA_ELLIPSOIDAL_HEIGHT"),
    ("EPHEMERIS_DERIVED", "ZERO_HEIGHT_ASSUMPTION"),
)


def _canonical_window_id(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.strip()
    valid = text.str.fullmatch(r"[0-9]+", na=False)
    if not bool(valid.all()):
        raise ValueError("window_id must be a positive canonical integer")
    numbers = text.astype("int64")
    if bool((numbers < 1).any()):
        raise ValueError("window_id must be a positive canonical integer")
    if bool((text != numbers.astype("string")).any()):
        raise ValueError("window_id must be a positive canonical integer")
    return numbers.astype("string")


def _normalise_identity(frame: pd.DataFrame, key: tuple[str, ...]) -> pd.DataFrame:
    result = frame.copy()
    missing = [column for column in key if column not in result.columns]
    if missing:
        raise ValueError(f"identity schema missing: {','.join(missing)}")
    result["run_id"] = result["run_id"].astype("string").str.strip()
    if bool(result["run_id"].isna().any()) or bool(result["run_id"].eq("").any()):
        raise ValueError("run_id must be nonempty")
    result["window_id"] = _canonical_window_id(result["window_id"])
    for column in ("scene_id", "environment_class", "prn", "tracking_channel"):
        if column in result.columns:
            result[column] = result[column].astype("string").fillna("").str.strip()
    return result


def build_wp3_population(path_rows: pd.DataFrame, window_rows: pd.DataFrame) -> pd.DataFrame:
    """Join all MPC to exactly one selected window and verify shared identity.

    Windows with zero MPC remain in the window input/support tables but do not
    become fabricated path rows. Every input path must be an MPC and every
    selected-window MPC count must reconcile to the path table.
    """
    path_required = set(MPC_KEY) | set(IDENTITY_TAGS) | {
        "is_multipath", *VARIABLE_FAMILIES.keys(), "elevation_source", "receiver_height_source"
    }
    window_required = set(WINDOW_KEY) | set(IDENTITY_TAGS) | {
        "mpc_count", "elevation_value_deg", "elevation_source", "receiver_height_source",
        "position_source", "receiver_speed_mps"
    }
    missing_path = sorted(path_required - set(path_rows.columns))
    missing_window = sorted(window_required - set(window_rows.columns))
    if missing_path or missing_window:
        raise ValueError(f"schema missing path={missing_path}; window={missing_window}")

    paths = _normalise_identity(path_rows, MPC_KEY)
    windows = _normalise_identity(window_rows, WINDOW_KEY)
    if windows.duplicated(list(WINDOW_KEY)).any():
        raise ValueError("duplicate window identity")
    if paths.duplicated(list(MPC_KEY)).any():
        raise ValueError("duplicate MPC identity")

    for frame, name in ((paths, "path"), (windows, "window")):
        for column in IDENTITY_TAGS:
            if bool(frame[column].isna().any()) or bool(frame[column].eq("").any()):
                raise ValueError(f"{name} identity tag {column} must be nonempty")

    paths["path_id"] = pd.to_numeric(paths["path_id"], errors="raise")
    if not bool(np.isfinite(paths["path_id"].to_numpy(dtype=float)).all()):
        raise ValueError("path_id must be finite")
    if bool((paths["path_id"] % 1 != 0).any()) or bool((paths["path_id"] < 1).any()):
        raise ValueError("path_id must be a positive integer")
    paths["path_id"] = paths["path_id"].astype("int64")
    paths["is_multipath"] = pd.to_numeric(paths["is_multipath"], errors="raise")
    if not bool(paths["is_multipath"].eq(1).all()):
        raise ValueError("WP3 path input must contain only Stage2 MPC rows")

    for column in ("elevation_source", "receiver_height_source"):
        paths[column] = paths[column].astype("string").fillna("").str.strip()
        windows[column] = windows[column].astype("string").fillna("").str.strip()
    windows["mpc_count"] = pd.to_numeric(windows["mpc_count"], errors="raise")
    if (not bool(np.isfinite(windows["mpc_count"].to_numpy(dtype=float)).all())
            or bool((windows["mpc_count"] < 0).any())
            or bool((windows["mpc_count"] % 1 != 0).any())):
        raise ValueError("mpc_count must be a nonnegative integer")
    windows["mpc_count"] = windows["mpc_count"].astype("int64")

    counts = paths.groupby(list(WINDOW_KEY), sort=False).size().rename("observed_mpc_count")
    declared = windows.set_index(list(WINDOW_KEY))["mpc_count"]
    observed = counts.reindex(declared.index, fill_value=0)
    if not observed.astype("int64").equals(declared.astype("int64")):
        raise ValueError("window MPC count does not reconcile to path rows")

    window_set = set(windows[list(WINDOW_KEY)].itertuples(index=False, name=None))
    path_window_set = set(paths[list(WINDOW_KEY)].itertuples(index=False, name=None))
    if not path_window_set.issubset(window_set):
        raise ValueError("MPC references a window absent from selected-window table")
    indexed_windows = windows.set_index(list(WINDOW_KEY), drop=False)
    for _, row in paths.iterrows():
        key = (row.run_id, row.window_id)
        window = indexed_windows.loc[key]
        for column in IDENTITY_TAGS:
            if str(row[column]) != str(window[column]):
                raise ValueError(f"path/window identity mismatch for {column}: {key}")
        for column in ("elevation_source", "receiver_height_source"):
            if str(row[column]) != str(window[column]):
                raise ValueError(f"path/window identity mismatch for {column}: {key}")

    condition_columns = [
        "elevation_value_deg", "position_source", "receiver_speed_mps", "position_status",
        "route_component_id", "route_cumulative_distance_m"
    ]
    included = [column for column in condition_columns if column in windows.columns]
    join_windows = windows[list(WINDOW_KEY) + ["mpc_count", *included]].copy()
    result = paths.merge(join_windows, on=list(WINDOW_KEY), how="left", validate="many_to_one", sort=False)
    result["elevation_value_deg"] = pd.to_numeric(result["elevation_value_deg"], errors="coerce")
    source = result["elevation_source"].astype(str)
    measured = source.eq("GSV_MEASURED")
    derived = source.eq("EPHEMERIS_DERIVED")
    missing = source.eq("MISSING")
    if not bool((measured | derived | missing).all()):
        raise ValueError("unsupported elevation source label")
    if bool((~np.isfinite(result.loc[measured, "elevation_value_deg"])).any()):
        raise ValueError("GSV measured elevation is not finite")
    if bool(((result.loc[measured, "elevation_value_deg"] < 0)
             | (result.loc[measured, "elevation_value_deg"] > 90)).any()):
        raise ValueError("GSV measured elevation is outside [0,90]")
    if bool((~np.isfinite(result.loc[derived, "elevation_value_deg"])).any()):
        raise ValueError("ephemeris-derived elevation is not finite")
    if bool(result.loc[derived, "receiver_height_source"].isin(
            ["GGA_ELLIPSOIDAL_HEIGHT", "ZERO_HEIGHT_ASSUMPTION"]).eq(False).any()):
        raise ValueError("ephemeris-derived elevation lacks a recognized height source")
    if bool(result.loc[missing, "elevation_value_deg"].notna().any()):
        raise ValueError("missing elevation source contains a numeric value")

    result["receiver_speed_mps"] = pd.to_numeric(result["receiver_speed_mps"], errors="coerce")
    return result


def make_scene_folds(frame: pd.DataFrame, environments: tuple[str, ...] | None = None) -> list[dict]:
    """Return deterministic complete-scene folds; never split windows/PRNs."""
    if "scene_id" not in frame or "environment_class" not in frame:
        raise ValueError("scene/environment labels are required for LOSO")
    selected = frame
    if environments is not None:
        selected = frame[frame.environment_class.isin(environments)]
    scenes = sorted(selected.scene_id.astype(str).unique())
    folds = []
    for scene in scenes:
        test = selected[selected.scene_id.astype(str) == scene].copy().reset_index(drop=True)
        train = selected[selected.scene_id.astype(str) != scene].copy().reset_index(drop=True)
        if train.empty or test.empty:
            raise ValueError(f"empty train/test rows for held-out scene {scene}")
        if set(train.scene_id.astype(str)) & set(test.scene_id.astype(str)):
            raise ValueError(f"scene leakage in held-out fold {scene}")
        folds.append({"held_out_scene_id": scene, "train": train, "test": test,
                      "training_scene_ids": tuple(sorted(train.scene_id.astype(str).unique()))})
    return folds


def condition_support_tables(
    population: pd.DataFrame,
    window_rows: pd.DataFrame,
    trajectory_rows: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Summarize scene support without dropping zero-MPC selected windows.

    If a trajectory overlay is supplied, speed source-record reuse is counted
    by its real source identity. The function does not interpolate, cap, or
    otherwise alter speed or elevation values.
    """
    windows = _normalise_identity(window_rows, WINDOW_KEY)
    if windows.duplicated(list(WINDOW_KEY)).any():
        raise ValueError("duplicate window identity in support input")
    for column in IDENTITY_TAGS:
        if column not in windows:
            raise ValueError(f"support window schema missing {column}")
    windows["elevation_source"] = windows["elevation_source"].astype("string").fillna("").str.strip()
    windows["receiver_height_source"] = windows["receiver_height_source"].astype("string").fillna("").str.strip()
    windows["mpc_count"] = pd.to_numeric(windows["mpc_count"], errors="raise").astype("int64")
    windows["elevation_value_deg"] = pd.to_numeric(windows["elevation_value_deg"], errors="coerce")

    if population.duplicated(list(MPC_KEY)).any():
        raise ValueError("duplicate MPC identity in support input")
    path_window_set = set(population[list(WINDOW_KEY)].astype("string").itertuples(index=False, name=None))
    window_set = set(windows[list(WINDOW_KEY)].itertuples(index=False, name=None))
    if not path_window_set.issubset(window_set):
        raise ValueError("support population references absent window")
    observed = population.groupby(list(WINDOW_KEY), sort=False).size()
    declared = windows.set_index(list(WINDOW_KEY))["mpc_count"]
    if not observed.reindex(declared.index, fill_value=0).astype("int64").equals(declared):
        raise ValueError("support MPC counts do not reconcile")
    indexed_windows_for_identity = windows.set_index(list(WINDOW_KEY), drop=False)
    for _, row in population.iterrows():
        window = indexed_windows_for_identity.loc[(row.run_id, row.window_id)]
        for column in IDENTITY_TAGS:
            if str(row[column]) != str(window[column]):
                raise ValueError(f"support identity mismatch for {column}")

    if trajectory_rows is not None:
        trajectory = _normalise_identity(trajectory_rows, WINDOW_KEY)
        if trajectory.duplicated(list(WINDOW_KEY)).any():
            raise ValueError("duplicate trajectory window identity")
        if set(trajectory[list(WINDOW_KEY)].itertuples(index=False, name=None)) != window_set:
            raise ValueError("trajectory window set mismatch")
        for column in ("scene_id",):
            if column not in trajectory:
                raise ValueError(f"trajectory identity schema missing {column}")
        if "environment_class" not in windows:
            raise ValueError("support window schema missing environment_class")
        for column in ("scene_id", "position_source"):
            if column not in windows or column not in trajectory:
                raise ValueError(f"trajectory schema missing {column}")
        indexed_trajectory = trajectory.set_index(list(WINDOW_KEY), drop=False)
        indexed_windows = windows.set_index(list(WINDOW_KEY), drop=False)
        for key in window_set:
            trow = indexed_trajectory.loc[key]
            wrow = indexed_windows.loc[key]
            for column in ("scene_id", "position_source"):
                if str(trow[column]) != str(wrow[column]):
                    raise ValueError(f"trajectory/window identity mismatch for {column}")
        trajectory_columns = ["position_source_record_id", "receiver_speed_mps"]
        if "receiver_speed_mps" not in trajectory:
            raise ValueError("trajectory speed field missing")
        selected = trajectory[list(WINDOW_KEY) + [c for c in trajectory_columns if c in trajectory]].copy()
        windows = windows.merge(selected, on=list(WINDOW_KEY), how="left", validate="one_to_one", sort=False,
                                suffixes=("", "_trajectory"))
        speed_col = "receiver_speed_mps_trajectory" if "receiver_speed_mps_trajectory" in windows else "receiver_speed_mps"
        if "receiver_speed_mps" in windows and speed_col != "receiver_speed_mps":
            left = pd.to_numeric(windows["receiver_speed_mps"], errors="coerce")
            right = pd.to_numeric(windows[speed_col], errors="coerce")
            comparable = left.notna() & right.notna()
            if bool((left[comparable] != right[comparable]).any()):
                raise ValueError("trajectory speed values disagree with selected-window table")
        windows["receiver_speed_mps"] = pd.to_numeric(windows[speed_col], errors="coerce")
    else:
        if "position_source_record_id" not in windows:
            windows["position_source_record_id"] = ""
        windows["receiver_speed_mps"] = pd.to_numeric(windows["receiver_speed_mps"], errors="coerce")

    path_counts = (population.groupby(["scene_id", "environment_class", "elevation_source",
                                      "receiver_height_source"], dropna=False)
                   .size().rename("mpc_n").reset_index())
    source_counts = (windows.groupby(["scene_id", "environment_class", "elevation_source",
                                     "receiver_height_source"], dropna=False)
                     .agg(window_n=("window_id", "size"), measured_min_deg=("elevation_value_deg", "min"),
                          measured_max_deg=("elevation_value_deg", "max"))
                     .reset_index())
    source = source_counts.merge(path_counts, how="left", on=["scene_id", "environment_class",
                                                               "elevation_source", "receiver_height_source"])
    source["mpc_n"] = source["mpc_n"].fillna(0).astype("int64")

    scene_rows = []
    for (scene, environment), group in windows.groupby(["scene_id", "environment_class"], sort=True):
        paths = population[population.scene_id.astype(str) == str(scene)]
        by_source_w = group.groupby("elevation_source").size().to_dict()
        by_source_p = paths.groupby("elevation_source").size().to_dict()
        derived = group[group.elevation_source == "EPHEMERIS_DERIVED"]
        scene_rows.append({
            "scene_id": str(scene), "environment_class": str(environment),
            "selected_window_n": int(len(group)), "mpc_n": int(group.mpc_count.sum()),
            "gsv_measured_window_n": int(by_source_w.get("GSV_MEASURED", 0)),
            "ephemeris_derived_window_n": int(by_source_w.get("EPHEMERIS_DERIVED", 0)),
            "ephemeris_gga_window_n": int((derived.receiver_height_source == "GGA_ELLIPSOIDAL_HEIGHT").sum()),
            "ephemeris_zero_height_window_n": int((derived.receiver_height_source == "ZERO_HEIGHT_ASSUMPTION").sum()),
            "missing_elevation_window_n": int(by_source_w.get("MISSING", 0)),
            "gsv_measured_mpc_n": int(by_source_p.get("GSV_MEASURED", 0)),
            "ephemeris_derived_mpc_n": int(by_source_p.get("EPHEMERIS_DERIVED", 0)),
            "missing_elevation_mpc_n": int(by_source_p.get("MISSING", 0)),
            "measured_elevation_min_deg": float(group.loc[group.elevation_source == "GSV_MEASURED",
                                                           "elevation_value_deg"].min())
                if (group.elevation_source == "GSV_MEASURED").any() else None,
            "measured_elevation_max_deg": float(group.loc[group.elevation_source == "GSV_MEASURED",
                                                           "elevation_value_deg"].max())
                if (group.elevation_source == "GSV_MEASURED").any() else None,
        })

    motion_rows = []
    for (scene, environment), group in windows.groupby(["scene_id", "environment_class"], sort=True):
        speed = group["receiver_speed_mps"].to_numpy(dtype=float)
        has_speed = np.isfinite(speed)
        nmea = group[(group.position_source == "EXISTING_NMEA") & np.isfinite(group.receiver_speed_mps)]
        pvt_no_speed = group[(group.position_source == "GNSS_SDR_PVT_SINGLE")
                             & ~np.isfinite(group.receiver_speed_mps)]
        missing_position = group[group.position_status.astype(str).str.contains("MISSING|UNAVAILABLE", regex=True)]
        ids = nmea["position_source_record_id"].astype("string").fillna("").str.strip()
        ids = ids[ids.ne("")]
        reuse = ids.value_counts()
        motion_rows.append({
            "scene_id": str(scene), "environment_class": str(environment),
            "selected_window_n": int(len(group)), "speed_available_window_n": int(has_speed.sum()),
            "nmea_speed_window_n": int(len(nmea)), "pvt_without_speed_window_n": int(len(pvt_no_speed)),
            "missing_position_window_n": int(len(missing_position)),
            "distinct_speed_source_record_n": int(ids.nunique()),
            "max_windows_per_speed_source_record": int(reuse.max()) if len(reuse) else 0,
            "distinct_speed_value_n": int(nmea.receiver_speed_mps.nunique()),
            "speed_min_mps": float(nmea.receiver_speed_mps.min()) if len(nmea) else None,
            "speed_median_mps": float(nmea.receiver_speed_mps.median()) if len(nmea) else None,
            "speed_max_mps": float(nmea.receiver_speed_mps.max()) if len(nmea) else None,
        })
    return pd.DataFrame(scene_rows), source, pd.DataFrame(motion_rows)


def scene_window_weights(frame: pd.DataFrame) -> np.ndarray:
    """Equalize total scene and selected-window weight; split within a window.

    Conditions are measured at window level. This pseudo-likelihood therefore
    gives each represented scene equal total weight and each MPC-bearing
    selected window within a scene equal weight, dividing that window's weight
    over its MPC rows. These are fitting weights, not independent-sample
    uncertainty weights.
    """
    required = {"scene_id", "run_id", "window_id"}
    if required - set(frame.columns):
        raise ValueError("scene/window identity is required for weights")
    if frame.empty:
        raise ValueError("cannot weight an empty frame")
    scenes = frame.scene_id.astype("string").str.strip()
    if bool(scenes.isna().any()) or bool(scenes.eq("").any()):
        raise ValueError("scene_id must be nonempty for weights")
    keys = pd.DataFrame({"scene_id": scenes, "run_id": frame.run_id.astype("string"),
                         "window_id": _canonical_window_id(frame.window_id)})
    scene_count = int(keys.scene_id.nunique())
    weights = np.zeros(len(frame), dtype=float)
    groups = keys.groupby(["scene_id", "run_id", "window_id"], sort=False).indices
    windows_by_scene = keys.drop_duplicates(["scene_id", "run_id", "window_id"]).groupby(
        "scene_id", sort=False).size().to_dict()
    for (scene, _run, _window), positions in groups.items():
        weight = 1.0 / scene_count / int(windows_by_scene[scene]) / len(positions)
        weights[np.asarray(positions, dtype=int)] = weight
    weights /= weights.sum()
    return weights


def _distribution_logpdf(family: str, values: np.ndarray, parameters: dict) -> np.ndarray:
    if family == "gamma":
        return stats.gamma.logpdf(values, a=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "lognormal":
        return stats.lognorm.logpdf(values, s=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min.logpdf(values, c=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm.logpdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace.logpdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t.logpdf(values, df=parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
    raise ValueError(f"unsupported distribution family: {family}")


def _distribution_ppf(family: str, quantile: float, parameters: dict) -> float:
    if family == "gamma":
        return float(stats.gamma.ppf(quantile, a=parameters["shape"], loc=0.0, scale=parameters["scale"]))
    if family == "lognormal":
        return float(stats.lognorm.ppf(quantile, s=parameters["shape"], loc=0.0, scale=parameters["scale"]))
    if family == "weibull":
        return float(stats.weibull_min.ppf(quantile, c=parameters["shape"], loc=0.0, scale=parameters["scale"]))
    if family == "normal":
        return float(stats.norm.ppf(quantile, loc=parameters["loc"], scale=parameters["scale"]))
    if family == "laplace":
        return float(stats.laplace.ppf(quantile, loc=parameters["loc"], scale=parameters["scale"]))
    if family == "student_t":
        return float(stats.t.ppf(quantile, df=parameters["df"], loc=parameters["loc"], scale=parameters["scale"]))
    raise ValueError(f"unsupported distribution family: {family}")


def _fit_static(values: np.ndarray, weights: np.ndarray, family: str) -> dict:
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if len(x) < 4 or len(x) != len(w) or not np.isfinite(x).all() or not np.isfinite(w).all():
        return {"status": "INSUFFICIENT_OR_NONFINITE_DATA", "parameters": {},
                "failure_reason": "requires at least four finite observations and matching finite weights"}
    if family not in {family_name for families in VARIABLE_FAMILIES.values() for family_name in families}:
        raise ValueError(f"unsupported distribution family: {family}")
    if family in {"gamma", "lognormal", "weibull"} and bool((x <= 0).any()):
        return {"status": "UNSUPPORTED_NONPOSITIVE_DATA", "parameters": {},
                "failure_reason": "positive-support candidate received zero or negative values"}
    w = w / w.sum()
    mean = float(np.dot(w, x))
    variance = float(np.dot(w, (x - mean) ** 2))
    if variance <= np.finfo(float).eps * max(1.0, mean * mean):
        return {"status": "CONSTANT_DATA", "parameters": {}, "failure_reason": "zero or near-zero weighted variance"}

    # These weighted MLEs have exact solutions. Using them avoids line-search
    # failures where numerical optimization adds no value, while retaining the
    # same scene/window-balanced pseudo-likelihood.
    if family == "normal":
        parameters = {"loc": mean, "scale": float(np.sqrt(variance))}
        log_score = float(np.dot(w, _distribution_logpdf(family, x, parameters)))
        return {"status": "PASS", "parameters": parameters, "failure_reason": "",
                "optimizer_message": "CLOSED_FORM_WEIGHTED_MLE", "weighted_log_score": log_score,
                "boundary_parameters": []}
    if family == "lognormal":
        lx = np.log(x)
        mu = float(np.dot(w, lx))
        shape = float(np.sqrt(np.dot(w, (lx - mu) ** 2)))
        if shape <= 0 or not np.isfinite(shape):
            return {"status": "CONSTANT_LOG_DATA", "parameters": {},
                    "failure_reason": "zero or non-finite weighted log variance"}
        parameters = {"shape": shape, "scale": float(np.exp(mu)), "loc": 0.0,
                      "log_scale": mu}
        log_score = float(np.dot(w, _distribution_logpdf(family, x, parameters)))
        return {"status": "PASS", "parameters": parameters, "failure_reason": "",
                "optimizer_message": "CLOSED_FORM_WEIGHTED_MLE", "weighted_log_score": log_score,
                "boundary_parameters": []}
    if family == "laplace":
        loc = _weighted_quantile(x, w, 0.5)
        scale = float(np.dot(w, np.abs(x - loc)))
        if scale <= 0 or not np.isfinite(scale):
            return {"status": "CONSTANT_DATA", "parameters": {},
                    "failure_reason": "zero or non-finite weighted absolute deviation"}
        parameters = {"loc": loc, "scale": scale}
        log_score = float(np.dot(w, _distribution_logpdf(family, x, parameters)))
        return {"status": "PASS", "parameters": parameters, "failure_reason": "",
                "optimizer_message": "CLOSED_FORM_WEIGHTED_MLE", "weighted_log_score": log_score,
                "boundary_parameters": []}

    if family in {"gamma", "weibull"}:
        if family == "gamma":
            theta0 = np.array([np.log(max(mean * mean / variance, 1e-5)),
                               np.log(max(variance / max(mean, 1e-10), 1e-10))])
        else:
            theta0 = np.array([np.log(1.5), np.log(max(mean, 1e-10))])
        bounds = [(-12.0, 8.0), (-20.0, 15.0)]

        def decode(theta):
            shape, log_scale = np.exp(theta[0]), theta[1]
            scale = float(np.exp(log_scale))
            return {"shape": float(shape), "scale": scale, "loc": 0.0, "log_scale": float(log_scale)}
    elif family in {"normal", "laplace"}:
        loc0 = mean if family == "normal" else float(np.median(x))
        scale0 = np.sqrt(variance) if family == "normal" else float(np.dot(w, np.abs(x - loc0)))
        theta0 = np.array([loc0, np.log(max(scale0, 1e-8))])
        bounds = [(None, None), (-20.0, 20.0)]

        def decode(theta):
            return {"loc": float(theta[0]), "scale": float(np.exp(theta[1]))}
    else:
        theta0 = np.array([np.log(10.0), mean, np.log(max(np.sqrt(variance), 1e-8))])
        bounds = [(np.log(0.2), np.log(10000.0)), (None, None), (-20.0, 20.0)]

        def decode(theta):
            return {"df": float(np.exp(theta[0])), "loc": float(theta[1]),
                    "scale": float(np.exp(theta[2]))}

    def objective(theta):
        lp = _distribution_logpdf(family, x, decode(theta))
        if not np.isfinite(lp).all():
            return 1e100
        return float(-np.dot(w, lp))

    result = optimize.minimize(objective, theta0, method="L-BFGS-B", bounds=bounds,
                               options={"maxiter": 3000, "ftol": 1e-12, "gtol": 1e-8})
    params = decode(result.x)
    close_to_bound = []
    for index, (lo, hi) in enumerate(bounds):
        if lo is not None and result.x[index] - lo < 1e-5:
            close_to_bound.append(f"theta_{index}_lower")
        if hi is not None and hi - result.x[index] < 1e-5:
            close_to_bound.append(f"theta_{index}_upper")
    valid = result.success and np.isfinite(result.fun) and all(np.isfinite(list(params.values())))
    return {
        "status": "PASS_WITH_BOUNDARY" if valid and close_to_bound else "PASS" if valid else "FAILED_OPTIMIZER",
        "parameters": params, "failure_reason": "" if valid else str(result.message),
        "optimizer_message": str(result.message), "weighted_log_score": float(-result.fun) if np.isfinite(result.fun) else None,
        "boundary_parameters": close_to_bound,
    }


def _validate_model_frame(frame: pd.DataFrame, variable: str) -> str | None:
    required = {variable, "scene_id", "environment_class", "run_id", "window_id"}
    if required - set(frame.columns):
        return f"missing columns: {sorted(required - set(frame.columns))}"
    if frame.empty:
        return "empty training data"
    values = pd.to_numeric(frame[variable], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        return f"non-finite {variable} in training data"
    return None


def fit_model(frame: pd.DataFrame, variable: str, family: str, model: str) -> dict:
    """Fit window/scene-balanced M0, environment M1, or source-specific M2.

    M2 uses a common elevation slope over both core environments, with an
    environment-specific intercept/scale/shape. For positive families the
    slope changes log-scale; for signed families it changes location.
    """
    if variable not in VARIABLE_FAMILIES or family not in VARIABLE_FAMILIES[variable]:
        raise ValueError(f"family {family} is not a WP1/WP2 candidate for {variable}")
    if model not in {"M0", "M1", "M2"}:
        raise ValueError("model must be M0, M1, or M2")
    error = _validate_model_frame(frame, variable)
    scene_ids = tuple(sorted(frame.scene_id.astype(str).unique())) if "scene_id" in frame else ()
    base = {"model": model, "family": family, "variable": variable,
            "training_scene_ids": scene_ids, "training_scene_n": len(scene_ids),
            "training_path_n": int(len(frame)),
            "training_window_n": int(frame[list(WINDOW_KEY)].drop_duplicates().shape[0])
                if set(WINDOW_KEY).issubset(frame.columns) else 0,
            "fit_weighting": "equal total scene; equal MPC-bearing window within scene; split window weight across MPC rows",
            "status": "FAILED", "parameters": {}, "failure_reason": error or ""}
    if error:
        return base
    x = pd.to_numeric(frame[variable], errors="raise").to_numpy(dtype=float)
    if model == "M0":
        base.update(_fit_static(x, scene_window_weights(frame), family))
        return base

    env_values = frame.environment_class.astype(str)
    if not set(env_values).issubset(set(CORE_ENVIRONMENTS)):
        base["failure_reason"] = "model training contains a non-core environment"
        return base
    environment_fits = {}
    for environment in CORE_ENVIRONMENTS:
        subset = frame[env_values == environment]
        if subset.empty:
            base["failure_reason"] = f"missing environment support: {environment}"
            return base
        if subset.scene_id.nunique() < 2:
            base["failure_reason"] = f"fewer than two training scenes for {environment}"
            base["status"] = "INSUFFICIENT_SCENES"
            return base
        fit = _fit_static(pd.to_numeric(subset[variable], errors="raise").to_numpy(dtype=float),
                          scene_window_weights(subset), family)
        if fit["status"] not in {"PASS", "PASS_WITH_BOUNDARY"}:
            base["failure_reason"] = f"{environment}: {fit['failure_reason']}"
            base["status"] = fit["status"]
            return base
        environment_fits[environment] = fit
    if model == "M1":
        boundary = {env: fit.get("boundary_parameters", []) for env, fit in environment_fits.items()}
        base.update(status="PASS_WITH_BOUNDARY" if any(boundary.values()) else "PASS",
                    parameters={"by_environment": {env: fit["parameters"] for env, fit in environment_fits.items()}},
                    optimizer_messages={env: fit.get("optimizer_message", "") for env, fit in environment_fits.items()},
                    boundary_parameters=boundary)
        return base

    if "elevation_value_deg" not in frame or "elevation_source" not in frame:
        base["status"] = "INSUFFICIENT_CONDITION_DATA"
        base["failure_reason"] = "M2 requires numeric elevation_value_deg and elevation_source"
        return base
    source = frame.elevation_source.astype("string").fillna("").str.strip()
    valid_source = source.isin(["GSV_MEASURED", "EPHEMERIS_DERIVED"])
    if not bool(valid_source.all()):
        base["status"] = "INSUFFICIENT_CONDITION_DATA"
        base["failure_reason"] = "M2 data must use one complete measured or derived elevation source"
        return base
    source_kinds = tuple(sorted(source.unique()))
    if len(source_kinds) != 1:
        base["status"] = "MIXED_ELEVATION_SOURCES"
        base["failure_reason"] = "M2 must not merge measured and derived elevation"
        return base
    if source_kinds[0] == "EPHEMERIS_DERIVED":
        heights = frame.receiver_height_source.astype("string").fillna("").str.strip().unique()
        if len(heights) != 1 or heights[0] not in {"GGA_ELLIPSOIDAL_HEIGHT", "ZERO_HEIGHT_ASSUMPTION"}:
            base["status"] = "MIXED_ELEVATION_SOURCES"
            base["failure_reason"] = "derived M2 must contain exactly one receiver-height source"
            return base
        height_source = str(heights[0])
    else:
        height_source = "NOT_APPLICABLE_GSV_MEASURED"
    elevation = pd.to_numeric(frame.elevation_value_deg, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(elevation).all() or bool(((elevation < 0) | (elevation > 90)).any()):
        base["status"] = "INSUFFICIENT_CONDITION_DATA"
        base["failure_reason"] = "M2 elevation must be finite and within [0,90]"
        return base

    # Parameters at 45 degrees: per-environment shape/scale (positive) or
    # location/scale (signed); one common slope per 10-degree increase.
    if family in {"gamma", "lognormal", "weibull"}:
        theta0 = np.array([
            np.log(environment_fits[env]["parameters"]["shape"]) for env in CORE_ENVIRONMENTS
        ] + [
            np.log(environment_fits[env]["parameters"]["scale"]) for env in CORE_ENVIRONMENTS
        ] + [0.0])
        bounds = [(-12.0, 8.0), (-12.0, 8.0), (-20.0, 15.0), (-20.0, 15.0), (-10.0, 10.0)]

        def decode_m2(theta, env, z):
            idx = CORE_ENVIRONMENTS.index(env)
            scale = np.exp(theta[2 + idx] + theta[4] * np.asarray(z, dtype=float))
            return {"shape": float(np.exp(theta[idx])),
                    "scale": float(scale) if np.ndim(scale) == 0 else scale, "loc": 0.0}
        slope_name = "log_scale_slope_per_10deg"
    else:
        theta0 = np.array([
            environment_fits[env]["parameters"]["loc"] for env in CORE_ENVIRONMENTS
        ] + [
            np.log(environment_fits[env]["parameters"]["scale"]) for env in CORE_ENVIRONMENTS
        ] + [0.0] + ([np.log(10.0)] if family == "student_t" else []))
        bounds = [(None, None), (None, None), (-20.0, 20.0), (-20.0, 20.0), (-1000.0, 1000.0)]
        if family == "student_t":
            bounds.append((np.log(0.2), np.log(10000.0)))

        def decode_m2(theta, env, z):
            idx = CORE_ENVIRONMENTS.index(env)
            loc = theta[idx] + theta[4] * np.asarray(z, dtype=float)
            params = {"loc": float(loc) if np.ndim(loc) == 0 else loc,
                      "scale": float(np.exp(theta[2 + idx]))}
            if family == "student_t":
                params["df"] = float(np.exp(theta[5]))
            return params
        slope_name = "location_slope_per_10deg"

    w = scene_window_weights(frame)
    env_array = env_values.to_numpy(dtype=str)
    z = (elevation - 45.0) / 10.0

    def objective(theta):
        lp = np.empty(len(frame), dtype=float)
        for environment in CORE_ENVIRONMENTS:
            mask = env_array == environment
            lp[mask] = _distribution_logpdf(family, x[mask],
                                             decode_m2(theta, environment, z[mask]))
        if not np.isfinite(lp).all():
            return 1e100
        return float(-np.dot(w, lp))

    result = optimize.minimize(objective, theta0, method="L-BFGS-B", bounds=bounds,
                               options={"maxiter": 5000, "ftol": 1e-12, "gtol": 1e-8})
    close = []
    for index, (lo, hi) in enumerate(bounds):
        if lo is not None and result.x[index] - lo < 1e-5:
            close.append(f"theta_{index}_lower")
        if hi is not None and hi - result.x[index] < 1e-5:
            close.append(f"theta_{index}_upper")
    valid = result.success and np.isfinite(result.fun)
    params = {
        "by_environment_at_45deg": {
            env: decode_m2(result.x, env, 0.0) for env in CORE_ENVIRONMENTS
        },
        "elevation_slope_type": slope_name,
        "elevation_slope_per_10deg": float(result.x[4]),
        "elevation_center_deg": 45.0,
        "elevation_source": source_kinds[0],
        "receiver_height_source": height_source,
    }
    if family == "student_t":
        params["shared_df"] = float(np.exp(result.x[5]))
        for env in CORE_ENVIRONMENTS:
            params["by_environment_at_45deg"][env]["df"] = params["shared_df"]
    base.update(status="PASS_WITH_BOUNDARY" if valid and close else "PASS" if valid else "FAILED_OPTIMIZER",
                parameters=params, optimizer_message=str(result.message), boundary_parameters=close,
                weighted_log_score=float(-result.fun) if np.isfinite(result.fun) else None)
    if not valid:
        base["failure_reason"] = str(result.message)
    return base


def _row_parameters(fit: dict, row: pd.Series) -> dict:
    model = fit["model"]
    family = fit["family"]
    parameters = fit["parameters"]
    if model == "M0":
        return parameters
    environment = str(row.environment_class)
    if model == "M1":
        return parameters["by_environment"][environment]
    params = parameters["by_environment_at_45deg"][environment].copy()
    z = (float(row.elevation_value_deg) - parameters["elevation_center_deg"]) / 10.0
    slope = float(parameters["elevation_slope_per_10deg"])
    if family in {"gamma", "lognormal", "weibull"}:
        params["scale"] = float(params["scale"] * np.exp(slope * z))
    else:
        params["loc"] = float(params["loc"] + slope * z)
    return params


def score_model(fit: dict, frame: pd.DataFrame, variable: str) -> dict:
    """Score held-out paths, giving each test window equal total weight."""
    result = {"status": "FAILED", "model": fit.get("model"), "family": fit.get("family"),
              "test_path_n": int(len(frame)),
              "test_window_n": int(frame[list(WINDOW_KEY)].drop_duplicates().shape[0])
                  if set(WINDOW_KEY).issubset(frame.columns) else 0,
              "window_balanced_mean_log_score": None, "mpc_row_mean_log_score": None,
              "support_violation_n": 0, "failure_reason": ""}
    if fit.get("status") not in {"PASS", "PASS_WITH_BOUNDARY"}:
        result["failure_reason"] = f"fit not usable: {fit.get('status')} {fit.get('failure_reason', '')}".strip()
        return result
    if frame.empty or variable not in frame:
        result["failure_reason"] = "empty test data or missing target"
        return result
    values = pd.to_numeric(frame[variable], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        result["failure_reason"] = "non-finite held-out target"
        return result
    family = fit["family"]
    if family in {"gamma", "lognormal", "weibull"}:
        violation = int((values <= 0).sum())
        result["support_violation_n"] = violation
        if violation:
            result["status"] = "SUPPORT_VIOLATION"
            result["failure_reason"] = "positive-support candidate cannot score nonpositive held-out values"
            return result
    try:
        logpdf = np.array([_distribution_logpdf(family, np.asarray([value]), _row_parameters(fit, row))[0]
                           for value, (_, row) in zip(values, frame.iterrows())], dtype=float)
        if not np.isfinite(logpdf).all():
            result["status"] = "NONFINITE_SCORE"
            result["failure_reason"] = "non-finite held-out log score"
            return result
        result["window_balanced_mean_log_score"] = float(np.dot(scene_window_weights(frame), logpdf))
        result["mpc_row_mean_log_score"] = float(np.mean(logpdf))
        result["status"] = "PASS"
    except (KeyError, ValueError, FloatingPointError) as exc:
        result["failure_reason"] = f"{type(exc).__name__}: {exc}"
    return result


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if (values.ndim != 1 or weights.ndim != 1 or len(values) != len(weights)
            or len(values) == 0 or not np.isfinite(values).all()
            or not np.isfinite(weights).all() or bool((weights < 0).any())
            or weights.sum() <= 0 or not 0 <= quantile <= 1):
        raise ValueError("weighted quantile needs finite values, nonnegative weights, and q in [0,1]")
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order]) / weights.sum()
    index = min(int(np.searchsorted(cumulative, quantile, side="left")), len(values) - 1)
    return float(sorted_values[index])


def quantile_diagnostics(fit: dict, frame: pd.DataFrame, variable: str,
                         quantiles: tuple[float, ...] = (0.05, 0.5, 0.95)) -> list[dict]:
    """Return descriptive held-out calibration; no row/path CI is implied."""
    if fit.get("status") not in {"PASS", "PASS_WITH_BOUNDARY"}:
        return [{"model": fit.get("model"), "family": fit.get("family"), "quantile": q,
                 "status": "FIT_UNAVAILABLE", "failure_reason": fit.get("failure_reason", "")}
                for q in quantiles]
    values = pd.to_numeric(frame[variable], errors="coerce").to_numpy(dtype=float)
    if frame.empty or not np.isfinite(values).all():
        return [{"model": fit["model"], "family": fit["family"], "quantile": q,
                 "status": "INVALID_TEST_DATA", "failure_reason": "empty or non-finite held-out values"}
                for q in quantiles]
    weights = scene_window_weights(frame)
    result = []
    for quantile in quantiles:
        predicted = np.array([_distribution_ppf(fit["family"], quantile, _row_parameters(fit, row))
                              for _, row in frame.iterrows()], dtype=float)
        within_window_coverage = float(np.dot(weights, (values <= predicted).astype(float)))
        expected_tail = float(len(values) * min(quantile, 1.0 - quantile))
        empirical = _weighted_quantile(values, weights, quantile)
        predicted_summary = _weighted_quantile(predicted, weights, 0.5)
        result.append({
            "model": fit["model"], "family": fit["family"], "variable": variable,
            "quantile": float(quantile), "test_path_n": int(len(frame)),
            "test_window_n": int(frame[list(WINDOW_KEY)].drop_duplicates().shape[0]),
            "empirical_heldout_quantile": empirical,
            "median_rowwise_predicted_quantile": predicted_summary,
            "median_prediction_minus_empirical": float(predicted_summary - empirical),
            "window_balanced_coverage": within_window_coverage,
            "nominal_tail_path_rows_not_effective_n": expected_tail,
            "uncertainty_claim": "DESCRIPTIVE_ONLY_PATHS_AND_OVERLAPPING_WINDOWS_ARE_DEPENDENT",
            "status": "DESCRIPTIVE",
        })
    return result


def _identity_digest(frame: pd.DataFrame) -> str:
    """Hash sorted exact MPC identities for paired-model auditability."""
    identities = sorted(
        (str(row.run_id), str(row.window_id), str(int(row.path_id)))
        for row in frame.itertuples(index=False)
    )
    payload = "\n".join("|".join(identity) for identity in identities).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _scene_json(frame: pd.DataFrame) -> str:
    return json.dumps(sorted(frame.scene_id.astype(str).unique().tolist()),
                      ensure_ascii=False, separators=(",", ":"))


def _loso_scopes(core: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Return all-MPC and source-pure subsets, keeping derived height strata apart."""
    scopes: list[tuple[str, pd.DataFrame]] = [("ALL_MPC", core)]
    sources = core.elevation_source.astype(str)
    gsv = core.loc[sources.eq("GSV_MEASURED")].copy()
    if not gsv.empty:
        scopes.append(("GSV_MEASURED", gsv))
    derived = core.loc[sources.eq("EPHEMERIS_DERIVED")]
    for height, label in (
        ("GGA_ELLIPSOIDAL_HEIGHT", "EPHEMERIS_GGA"),
        ("ZERO_HEIGHT_ASSUMPTION", "EPHEMERIS_ZERO_HEIGHT"),
    ):
        subset = derived.loc[derived.receiver_height_source.astype(str).eq(height)].copy()
        if not subset.empty:
            scopes.append((label, subset))
    return scopes


def evaluate_scene_loso(
    frame: pd.DataFrame,
    families: dict[str, tuple[str, ...]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate paired core-scene LOSO for M0/M1 and source-pure M2.

    Rows remain MPCs for the conditional distribution, but the fitting and
    scoring weights give equal total weight to each scene and then each
    MPC-bearing window within a scene. This is a scene/window-balanced
    pseudo-likelihood and predictive score, not an independent-row likelihood
    or confidence interval. The held-out identities are hashed and identical
    across the models compared within each variable/family/scope/fold.

    Returns score rows, one fold manifest row per scope/variable/family/held
    scene, and descriptive p05/p50/p95 calibration rows. Unsupported folds
    are retained with explicit statuses rather than dropped.
    """
    required = set(MPC_KEY) | {"scene_id", "environment_class"} | set(VARIABLE_FAMILIES) | {
        "elevation_source", "receiver_height_source", "elevation_value_deg"
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"LOSO frame missing columns: {missing}")
    if frame.duplicated(list(MPC_KEY)).any():
        raise ValueError("LOSO frame contains duplicate MPC identity")
    core = frame.loc[frame.environment_class.astype(str).isin(CORE_ENVIRONMENTS)].copy()
    if core.empty:
        raise ValueError("LOSO core population is empty")
    scene_ids = sorted(core.scene_id.astype(str).unique().tolist())
    if len(scene_ids) < 3:
        raise ValueError("LOSO requires at least three core scenes")
    selected_families = families or VARIABLE_FAMILIES

    score_rows: list[dict] = []
    fold_rows: list[dict] = []
    tail_rows: list[dict] = []
    for scope_name, scope_frame in _loso_scopes(core):
        for variable, defaults in VARIABLE_FAMILIES.items():
            if families is not None and variable not in families:
                continue
            requested = tuple(selected_families.get(variable, defaults))
            for family in requested:
                if family not in defaults:
                    raise ValueError(f"family {family} is not a frozen candidate for {variable}")
                for held_scene in scene_ids:
                    test = scope_frame.loc[scope_frame.scene_id.astype(str).eq(held_scene)].copy()
                    train = scope_frame.loc[~scope_frame.scene_id.astype(str).eq(held_scene)].copy()
                    identity_sha = _identity_digest(test)
                    fold_status = "READY" if not test.empty else "NO_TEST_SUPPORT"
                    fold = {
                        "data_scope": scope_name,
                        "variable": variable,
                        "family": family,
                        "held_out_scene_id": held_scene,
                        "held_out_environment": str(
                            core.loc[core.scene_id.astype(str).eq(held_scene), "environment_class"].iloc[0]
                        ),
                        "training_scene_ids": _scene_json(train),
                        "test_scene_ids": _scene_json(test),
                        "training_scene_n": int(train.scene_id.nunique()),
                        "test_scene_n": int(test.scene_id.nunique()),
                        "training_path_n": int(len(train)),
                        "training_window_n": int(train[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                        "test_path_n": int(len(test)),
                        "test_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                        "test_identity_sha256": identity_sha,
                        "status": fold_status,
                        "uncertainty_claim": "NO_INDEPENDENT_FOLD_CI;_LOSO_TRAINING_SETS_OVERLAP",
                    }
                    fold_rows.append(fold)
                    models = ("M0", "M1") if scope_name == "ALL_MPC" else ("M0", "M1", "M2")
                    for model in models:
                        fitted = fit_model(train, variable, family, model)
                        if test.empty:
                            scored = {
                                "status": "NO_TEST_SUPPORT", "model": model, "family": family,
                                "test_path_n": 0, "test_window_n": 0,
                                "window_balanced_mean_log_score": None,
                                "mpc_row_mean_log_score": None,
                                "support_violation_n": 0,
                                "failure_reason": "held-out scene has no MPC in this data scope",
                            }
                        else:
                            scored = score_model(fitted, test, variable)
                        score_rows.append({
                            "data_scope": scope_name,
                            "variable": variable,
                            "family": family,
                            "held_out_scene_id": held_scene,
                            "held_out_environment": fold["held_out_environment"],
                            "model": model,
                            "fit_status": fitted.get("status"),
                            "fit_failure_reason": fitted.get("failure_reason", ""),
                            "fit_parameters_json": json.dumps(
                                fitted.get("parameters", {}), ensure_ascii=False,
                                sort_keys=True, separators=(",", ":"), allow_nan=False,
                            ),
                            "training_scene_ids": _scene_json(train),
                            "training_path_n": int(len(train)),
                            "training_window_n": int(train[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                            "test_identity_sha256": identity_sha,
                            "score_status": scored["status"],
                            "score_failure_reason": scored.get("failure_reason", ""),
                            "test_path_n": scored.get("test_path_n", 0),
                            "test_window_n": scored.get("test_window_n", 0),
                            "window_balanced_mean_log_score": scored.get("window_balanced_mean_log_score"),
                            "mpc_row_mean_log_score": scored.get("mpc_row_mean_log_score"),
                            "support_violation_n": scored.get("support_violation_n", 0),
                            "fit_weighting": "SCENE_WINDOW_BALANCED_PSEUDO_LIKELIHOOD",
                            "score_weighting": "EQUAL_TEST_WINDOW_WITHIN_HELD_SCENE",
                        })
                        if not test.empty:
                            diagnostics = quantile_diagnostics(fitted, test, variable)
                            for diagnostic in diagnostics:
                                tail_rows.append({
                                    "data_scope": scope_name,
                                    "variable": variable,
                                    "family": family,
                                    "held_out_scene_id": held_scene,
                                    "held_out_environment": fold["held_out_environment"],
                                    "test_identity_sha256": identity_sha,
                                    "training_scene_ids": _scene_json(train),
                                    **diagnostic,
                                })
    return pd.DataFrame(score_rows), pd.DataFrame(fold_rows), pd.DataFrame(tail_rows)
