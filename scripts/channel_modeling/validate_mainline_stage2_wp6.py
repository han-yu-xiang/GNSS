"""Independent WP6 output validator (does not import the fitting module)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


FEATURES_SHA256 = "258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4"
MPC_SHA256 = "8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b"
WINDOW_KEY = ["run_id", "window_id"]
MPC_KEY = ["run_id", "window_id", "path_id"]
MARK_COLUMNS = ["excess_delay_chips", "doppler_offset_hz", "relative_power_db"]
PDP_TARGETS = ["pdp_rms_width_code_delay_samples", "pdp_peak_minus_sage_direct_delay_samples"]
TAIL_QUANTILES = (0.01, 0.05, 0.10, 0.90, 0.95, 0.99)
FROZEN_CONTRACT = {"window_n": 7847, "mpc_n": 8914, "scene_n": 13, "count_support": (0, 1, 2, 3)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path, label):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"required {label} output is missing: {path}")
    return pd.read_csv(path, dtype={key: "string" for key in
                                   ("run_id", "window_id", "path_id", "scene_id",
                                    "outer_held_out_scene_id")})


def _require(frame, columns, label):
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"{label} missing required columns: {sorted(missing)}")


def _keys(frame, columns, label):
    _require(frame, columns, label)
    result = frame[columns].copy()
    for column in columns:
        if result[column].isna().any() or result[column].astype("string").str.strip().eq("").any():
            raise ValueError(f"{label} contains missing identity {column}")
        result[column] = result[column].astype("string").str.strip()
    if result.duplicated(columns).any():
        raise ValueError(f"{label} contains duplicate identity keys")
    return result


def _parse_string_list(value, label):
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not a JSON string array") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{label} is not a JSON string array")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{label} contains duplicate scene IDs")
    return set(parsed)


def _as_numeric(frame, column, label, allow_nan=False):
    if column not in frame:
        raise ValueError(f"{label} missing numeric field {column}")
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    if not allow_nan and (not np.isfinite(values).all()):
        raise ValueError(f"{label}.{column} has missing or nonfinite values")
    return values


def _validate_source_contract(features, mpcs, contract):
    _require(features, WINDOW_KEY + ["scene_id", "stage2_mpc_count", "pdp_peak_at_grid_boundary",
                                    *PDP_TARGETS], "frozen feature input")
    _require(mpcs, MPC_KEY + ["scene_id", *MARK_COLUMNS], "frozen MPC input")
    window_keys = _keys(features, WINDOW_KEY, "frozen feature input")
    path_keys = _keys(mpcs, MPC_KEY, "frozen MPC input")
    if features.duplicated(WINDOW_KEY).any() or mpcs.duplicated(MPC_KEY).any():
        raise ValueError("frozen inputs contain duplicate identities")
    counts = _as_numeric(features, "stage2_mpc_count", "frozen feature input")
    if (counts < 0).any() or not np.array_equal(counts, np.rint(counts)):
        raise ValueError("frozen Stage2 window counts are invalid")
    support = set(int(value) for value in contract["count_support"])
    if not set(np.rint(counts).astype(int)).issubset(support):
        raise ValueError("frozen Stage2 counts exceed declared support")
    scenes = features["scene_id"].astype("string").str.strip()
    if scenes.isna().any() or scenes.eq("").any():
        raise ValueError("frozen feature input has missing scene identity")
    if len(window_keys) != int(contract["window_n"]):
        raise ValueError(f"source window count mismatch: {len(window_keys)}")
    if len(path_keys) != int(contract["mpc_n"]):
        raise ValueError(f"source MPC count mismatch: {len(path_keys)}")
    if scenes.nunique() != int(contract["scene_n"]):
        raise ValueError(f"source scene count mismatch: {scenes.nunique()}")
    rms = _as_numeric(features, "pdp_rms_width_code_delay_samples", "features")
    if (rms < 0).any():
        raise ValueError("PDP RMS values cannot be negative")
    for target in PDP_TARGETS[1:]:
        _as_numeric(features, target, "features")
    for column in MARK_COLUMNS:
        _as_numeric(mpcs, column, "MPCs")
    delay_samples = _as_numeric(mpcs, "excess_delay_samples", "MPCs")
    delay_chips = _as_numeric(mpcs, "excess_delay_chips", "MPCs")
    if not np.allclose(delay_samples, 10.0 * delay_chips, rtol=1e-9, atol=1e-8):
        raise ValueError("frozen delay samples disagree with the source 10-samples/chip conversion")
    declared = pd.Series(np.rint(counts).astype(int), index=pd.MultiIndex.from_frame(window_keys))
    observed = pd.Series(1, index=pd.MultiIndex.from_frame(path_keys)).groupby(level=[0, 1]).sum()
    if not observed.index.isin(declared.index).all():
        raise ValueError("MPC identity references an unknown selected window")
    scene_by_window = pd.Series(scenes.to_numpy(), index=pd.MultiIndex.from_frame(window_keys))
    path_scenes = pd.Series(mpcs["scene_id"].astype("string").str.strip().to_numpy(),
                            index=pd.MultiIndex.from_frame(path_keys[WINDOW_KEY]))
    expected_scenes = scene_by_window.reindex(path_scenes.index)
    if not path_scenes.equals(expected_scenes):
        raise ValueError("MPC scene identity disagrees with source window")
    actual = observed.reindex(declared.index, fill_value=0).astype(int)
    if not actual.equals(declared):
        raise ValueError("frozen window MPC counts do not reconcile to path identities")
    return window_keys, path_keys, scenes


def _validate_manifest(output, features_path, mpcs_path, expected_hashes):
    manifest_path = Path(output) / "input_code_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("input_code_manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = manifest.get("source_inputs", {})
    for label, path, expected in (("features", features_path, expected_hashes["features"]),
                                  ("mpcs", mpcs_path, expected_hashes["mpcs"])):
        record = source.get(label)
        if not isinstance(record, dict):
            raise ValueError(f"provenance manifest missing source input {label}")
        actual = _sha256(path)
        if actual.lower() != str(expected).lower() or actual.lower() != str(record.get("sha256", "")).lower():
            raise ValueError(f"{label} input SHA does not match the frozen/manifest identity")
        if int(record.get("rows", -1)) < 0:
            raise ValueError(f"{label} row count is invalid in provenance manifest")
    code_root = Path(manifest.get("code_root", ""))
    code_files = manifest.get("code_files")
    if not isinstance(code_files, dict) or not code_files:
        raise ValueError("provenance manifest has no code-file identities")
    for relative, record in code_files.items():
        if not isinstance(record, dict):
            raise ValueError(f"invalid code provenance record for {relative}")
        code_path = Path(record.get("path", code_root / relative))
        recorded_hash = str(record.get("sha256", "")).lower()
        if len(recorded_hash) != 64 or any(char not in "0123456789abcdef" for char in recorded_hash):
            raise ValueError(f"invalid recorded code SHA-256 for {relative}")
        # The validator is not part of result generation. Its exact executed version
        # is recorded in independent_validation.json below; analytical code stays pinned.
        is_validator = Path(relative).name == Path(__file__).name
        if not is_validator and (not code_path.is_file() or _sha256(code_path).lower() != recorded_hash):
            raise ValueError(f"WP6 source code SHA changed after the recorded run: {relative}")
    return manifest


def _expected_scene_training(all_scenes, heldout):
    return set(all_scenes).difference({heldout})


def _validate_loso_table(frame, label, keys, expected_key_set, scene_by_key, all_scenes,
                         heldout_column="outer_held_out_scene_id"):
    _require(frame, list(keys) + ["scene_id", heldout_column, "training_scene_ids"], label)
    key_frame = _keys(frame, keys, label)
    if set(map(tuple, key_frame.itertuples(index=False, name=None))) != expected_key_set:
        raise ValueError(f"{label} keys do not match the expected population")
    for row in frame.itertuples(index=False):
        heldout = str(getattr(row, heldout_column))
        identity = tuple(str(getattr(row, key)) for key in keys)
        expected_scene = scene_by_key[identity]
        if str(row.scene_id) != expected_scene or heldout != expected_scene:
            raise ValueError(f"{label} held-out scene/fold identity mismatch")
        training = _parse_string_list(row.training_scene_ids, f"{label}.training_scene_ids")
        if training != _expected_scene_training(all_scenes, heldout):
            raise ValueError(f"{label} training scene leakage or omission in fold {heldout}")
    return frame


def _recompute_window_delay_summaries(features, mpcs):
    rows = []
    grouped = {key: group for key, group in mpcs.groupby(WINDOW_KEY, sort=False)}
    for row in features.itertuples(index=False):
        key = (str(row.run_id), str(row.window_id))
        group = grouped.get(key)
        if group is None or group.empty:
            centroid, spread, power_sum = 0.0, 0.0, 1.0
        else:
            delays = np.concatenate(([0.0], pd.to_numeric(group.excess_delay_samples).to_numpy(float)))
            powers = np.concatenate(([1.0], np.power(10.0, pd.to_numeric(group.relative_power_db).to_numpy(float) / 10.0)))
            power_sum = float(powers.sum())
            if not np.isfinite(powers).all() or power_sum <= 0:
                raise ValueError(f"invalid direct-plus-MPC relative power for {key}")
            centroid = float(np.dot(powers, delays) / power_sum)
            spread = float(np.sqrt(np.dot(powers, (delays - centroid) ** 2) / power_sum))
        rows.append({"run_id": key[0], "window_id": key[1], "scene_id": str(row.scene_id),
                     "stage2_mpc_count": int(row.stage2_mpc_count),
                     "pdp_peak_at_grid_boundary": row.pdp_peak_at_grid_boundary,
                     "pdp_rms_width_code_delay_samples": float(row.pdp_rms_width_code_delay_samples),
                     "pdp_peak_minus_sage_direct_delay_samples": float(
                         row.pdp_peak_minus_sage_direct_delay_samples),
                     "sage_relative_power_delay_centroid_samples": centroid,
                     "sage_relative_power_delay_rms_samples": spread,
                     "sage_direct_plus_mpc_relative_power_sum": power_sum})
    return pd.DataFrame(rows)


def validate_result_package(output_dir, features_path, mpc_path, expected_hashes=None,
                            expected_contract=None):
    """Recompute key population and delay arithmetic without importing WP6 code."""
    output = Path(output_dir)
    expected_hashes = {"features": FEATURES_SHA256, "mpcs": MPC_SHA256} if expected_hashes is None else dict(expected_hashes)
    if set(expected_hashes) != {"features", "mpcs"}:
        raise ValueError("expected_hashes must contain exactly features and mpcs")
    contract = dict(FROZEN_CONTRACT if expected_contract is None else expected_contract)
    for required in ("window_n", "mpc_n", "scene_n", "count_support"):
        if required not in contract:
            raise ValueError(f"expected_contract missing {required}")
    features_path, mpc_path = Path(features_path), Path(mpc_path)
    manifest = _validate_manifest(output, features_path, mpc_path, expected_hashes)
    features = pd.read_csv(features_path, dtype={key: "string" for key in WINDOW_KEY + ["scene_id"]})
    mpcs = pd.read_csv(mpc_path, dtype={key: "string" for key in MPC_KEY + ["scene_id"]})
    window_keys, path_keys, scenes = _validate_source_contract(features, mpcs, contract)
    scene_by_window = dict(zip(map(tuple, window_keys.itertuples(index=False, name=None)),
                               scenes.astype("string").str.strip().tolist()))
    all_scenes = set(scenes.astype("string").str.strip().tolist())
    mark_scenes = set(mpcs["scene_id"].astype("string").str.strip().tolist())
    window_key_set = set(scene_by_window)
    path_key_set = set(map(tuple, path_keys.itertuples(index=False, name=None)))
    summary_path = output / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError("summary.json is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    execution_path = output / "execution_record.json"
    if not execution_path.is_file():
        raise FileNotFoundError("execution_record.json is missing")
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    if execution.get("status") != "COMPLETE":
        raise ValueError("execution record does not attest a completed WP6 run")
    if int(manifest["source_inputs"]["features"].get("rows", -1)) != len(features):
        raise ValueError("feature source row count differs from provenance manifest")
    if int(manifest["source_inputs"]["mpcs"].get("rows", -1)) != len(mpcs):
        raise ValueError("MPC source row count differs from provenance manifest")
    for key, actual in (("window_n", len(window_keys)), ("mpc_n", len(path_keys)),
                        ("scene_n", len(all_scenes))):
        if int(summary.get(key, -1)) != actual:
            raise ValueError(f"summary population {key} mismatch")

    delay_path = _read_csv(output / "selected_window_delay_summaries.csv", "delay summaries")
    _require(delay_path, WINDOW_KEY + ["scene_id", "stage2_mpc_count", "pdp_peak_at_grid_boundary",
                                      *PDP_TARGETS, "sage_relative_power_delay_centroid_samples",
                                      "sage_relative_power_delay_rms_samples",
                                      "sage_direct_plus_mpc_relative_power_sum"], "delay summaries")
    delay_keys = _keys(delay_path, WINDOW_KEY, "delay summaries")
    if set(map(tuple, delay_keys.itertuples(index=False, name=None))) != window_key_set:
        raise ValueError("delay summaries omit or add selected-window identity")
    recomputed = _recompute_window_delay_summaries(features, mpcs)
    joined = recomputed.merge(delay_path, on=WINDOW_KEY, how="outer", validate="one_to_one",
                              suffixes=("_expected", "_actual"), indicator=True)
    if not joined._merge.eq("both").all():
        raise ValueError("delay summary identity mismatch")
    for column in ("scene_id", "stage2_mpc_count", "pdp_peak_at_grid_boundary", *PDP_TARGETS):
        if column not in PDP_TARGETS and not joined[f"{column}_expected"].astype(str).equals(
                joined[f"{column}_actual"].astype(str)):
            raise ValueError(f"delay summary source attribute mismatch: {column}")
    for column in PDP_TARGETS:
        expected = pd.to_numeric(joined[f"{column}_expected"], errors="coerce").to_numpy(float)
        actual = pd.to_numeric(joined[f"{column}_actual"], errors="coerce").to_numpy(float)
        if not np.isfinite(expected).all() or not np.isfinite(actual).all() or not np.allclose(
                expected, actual, rtol=1e-12, atol=1e-12):
            raise ValueError(f"delay summary source attribute mismatch beyond CSV precision: {column}")
    arithmetic_columns = ("sage_relative_power_delay_centroid_samples",
                          "sage_relative_power_delay_rms_samples",
                          "sage_direct_plus_mpc_relative_power_sum")
    max_delay_error = {}
    for column in arithmetic_columns:
        actual = pd.to_numeric(joined[f"{column}_actual"], errors="coerce").to_numpy(float)
        expected = pd.to_numeric(joined[f"{column}_expected"], errors="coerce").to_numpy(float)
        if not np.isfinite(actual).all():
            raise ValueError(f"delay summary {column} contains nonfinite values")
        error = np.abs(actual - expected)
        max_delay_error[column] = float(error.max(initial=0.0))
        if not np.allclose(actual, expected, rtol=1e-10, atol=1e-9):
            raise ValueError(f"independent delay arithmetic mismatch: {column}")

    count = _read_csv(output / "count_window_scores.csv", "count window scores")
    _require(count, WINDOW_KEY + ["scene_id", "outer_held_out_scene_id",
                                   "stage2_mpc_count", "status", "predicted_probability", "log_score"],
             "count window scores")
    count_keys = _keys(count, WINDOW_KEY, "count window scores")
    if set(map(tuple, count_keys.itertuples(index=False, name=None))) != window_key_set:
        raise ValueError("count scores omit or add selected windows")
    count_scene_map = dict(zip(map(tuple, window_keys.itertuples(index=False, name=None)),
                              scenes.astype("string").str.strip().tolist()))
    if not count.scene_id.astype(str).equals(count.outer_held_out_scene_id.astype(str)):
        raise ValueError("count window scene and held-out fold identity mismatch")
    if not count.scene_id.astype(str).isin(all_scenes).all():
        raise ValueError("count window score contains an unknown scene")
    for row in count.itertuples(index=False):
        identity = tuple(str(getattr(row, key)) for key in WINDOW_KEY)
        if str(row.scene_id) != count_scene_map[identity]:
            raise ValueError("count window scene does not match source window scene identity")
    expected_counts = dict(zip(map(tuple, window_keys.itertuples(index=False, name=None)),
                               np.rint(_as_numeric(features, "stage2_mpc_count", "features")).astype(int)))
    if any(int(row.stage2_mpc_count) != expected_counts[tuple(str(getattr(row, k)) for k in WINDOW_KEY)]
           for row in count.itertuples(index=False)):
        raise ValueError("count scores changed the source Stage2 MPC count")
    if len(count) != len(window_keys):
        raise ValueError("count window scores must retain every selected window exactly once")
    count_folds = _read_csv(output / "count_folds.csv", "count folds")
    _require(count_folds, ["held_out_scene_id", "training_scene_ids", "test_window_n", "fit_status"],
             "count folds")
    if set(count_folds.held_out_scene_id.astype(str)) != all_scenes or count_folds.held_out_scene_id.duplicated().any():
        raise ValueError("count folds do not contain exactly one held-out fold per selected-window scene")
    count_training_by_scene = {}
    for row in count_folds.itertuples(index=False):
        held = str(row.held_out_scene_id)
        training_scenes = _parse_string_list(row.training_scene_ids, "count_folds.training_scene_ids")
        if training_scenes != all_scenes - {held}:
            raise ValueError(f"count fold training scene leakage or omission: {held}")
        count_training_by_scene[held] = training_scenes
        if int(row.test_window_n) != int((scenes.astype("string").str.strip() == held).sum()):
            raise ValueError(f"count fold window support mismatch: {held}")
        if count.loc[count.outer_held_out_scene_id.astype(str).eq(held)].empty:
            raise ValueError(f"count window scores omit held-out scene {held}")
    support = sorted(int(value) for value in contract["count_support"])
    probability_table = _read_csv(output / "count_probabilities.csv", "count probabilities")
    _require(probability_table, ["outer_held_out_scene_id", "training_scene_ids",
                                 "count_category", "probability"],
             "count probabilities")
    if probability_table.duplicated(["outer_held_out_scene_id", "count_category"]).any():
        raise ValueError("duplicate count probability record")
    for held_scene in all_scenes:
        training_mask = scenes.astype("string").str.strip().ne(held_scene)
        training = features.loc[training_mask].copy()
        per_scene = []
        for _, scene_frame in training.groupby("scene_id", sort=True):
            frequencies = scene_frame["stage2_mpc_count"].astype(int).value_counts(normalize=True)
            per_scene.append({category: float(frequencies.get(category, 0.0)) for category in support})
        probabilities = {category: float(np.mean([row[category] for row in per_scene]))
                         for category in support}
        probability_rows = probability_table.loc[
            probability_table.outer_held_out_scene_id.astype(str).eq(held_scene)]
        if set(pd.to_numeric(probability_rows.count_category, errors="coerce").astype(int)) != set(support):
            raise ValueError(f"count probability table omits a category for {held_scene}")
        for probability_row in probability_rows.itertuples(index=False):
            if _parse_string_list(probability_row.training_scene_ids,
                                  "count_probabilities.training_scene_ids") != count_training_by_scene[held_scene]:
                raise ValueError(f"count probability training scene mismatch for {held_scene}")
            category = int(probability_row.count_category)
            if not np.isclose(float(probability_row.probability), probabilities[category],
                              rtol=1e-12, atol=1e-12):
                raise ValueError(f"count probability does not independently reconcile for {held_scene}")
        fold_rows = count.loc[count.outer_held_out_scene_id.astype(str).eq(held_scene)]
        if len(fold_rows) != int((scenes.astype("string").str.strip() == held_scene).sum()):
            raise ValueError(f"count fold window support mismatch: {held_scene}")
        for row in fold_rows.itertuples(index=False):
            category = int(row.stage2_mpc_count)
            expected_probability = probabilities[category]
            if not np.isclose(float(row.predicted_probability), expected_probability, rtol=1e-12, atol=1e-12):
                raise ValueError("count fold probability does not match independent scene-macro estimate")
            if expected_probability == 0.0:
                if str(row.status) != "UNSUPPORTED_COUNT_CATEGORY" or pd.notna(row.log_score):
                    raise ValueError("unsupported count category was smoothed or assigned a finite score")
            elif str(row.status) != "SCORED" or not np.isclose(float(row.log_score), np.log(expected_probability),
                                                                  rtol=1e-12, atol=1e-12):
                raise ValueError("count window log score does not match its predicted probability")

    mark_windows = _read_csv(output / "mark_window_scores.csv", "mark window scores")
    _require(mark_windows, ["path_n", "status", "product_score_status", "copula_score_status",
                            "product_marginal_log_score", "gaussian_copula_log_score"],
             "mark window scores")
    mark_window_keys = set(map(tuple, mpcs[WINDOW_KEY].drop_duplicates().itertuples(index=False, name=None)))
    _validate_loso_table(mark_windows, "mark window scores", WINDOW_KEY, mark_window_keys,
                         scene_by_window, mark_scenes)
    if len(mark_windows) != len(mark_window_keys):
        raise ValueError("mark scores must retain each MPC-bearing selected window once")
    expected_path_counts = mpcs.groupby(WINDOW_KEY).size().to_dict()
    for row in mark_windows.itertuples(index=False):
        identity = (str(row.run_id), str(row.window_id))
        if int(row.path_n) != int(expected_path_counts[identity]):
            raise ValueError(f"mark score path count changed for {identity}")

    mark_scene_scores = _read_csv(output / "mark_scene_scores.csv", "mark scene scores")
    _require(mark_scene_scores, ["outer_held_out_scene_id", "scene_id", "window_n", "status",
                                 "product_marginal_mean_window_log_score",
                                 "gaussian_copula_mean_window_log_score"], "mark scene scores")
    if len(mark_scene_scores) != len(mark_scenes):
        raise ValueError("mark scene score table must retain one row per held-out scene")
    for row in mark_scene_scores.itertuples(index=False):
        held = str(row.outer_held_out_scene_id)
        if str(row.scene_id) != held or held not in mark_scenes:
            raise ValueError("mark scene score identity does not match its outer fold")
        actual_window_n = int(mark_windows.outer_held_out_scene_id.astype(str).eq(held).sum())
        # The score table counts MPC-bearing windows, not all selected windows.
        if int(row.window_n) != actual_window_n:
            raise ValueError(f"mark scene score window support mismatch for {held}")
        matching = mark_windows.loc[mark_windows.outer_held_out_scene_id.astype(str).eq(held)]
        metric_contract = (
            ("product_score_status", "product_marginal_log_score",
             "product_marginal_mean_window_log_score"),
            ("copula_score_status", "gaussian_copula_log_score",
             "gaussian_copula_mean_window_log_score"),
        )
        for status_col, source_col, target_col in metric_contract:
            scene_status = str(getattr(row, status_col))
            window_status = matching[status_col].astype(str)
            if scene_status == "SCORED":
                if not window_status.eq("SCORED").all():
                    raise ValueError(f"mark scene {status_col} disagrees with its window rows: {held}")
                actual_score = pd.to_numeric(matching[source_col], errors="coerce")
                if not np.isfinite(actual_score.to_numpy(dtype=float)).all() or not np.isclose(
                        float(actual_score.mean()), float(getattr(row, target_col)),
                        rtol=1e-10, atol=1e-9):
                    raise ValueError(f"mark scene score does not aggregate its per-window rows: {held}")
            elif window_status.eq("SCORED").all():
                raise ValueError(f"mark scene {status_col} discards fully scored window rows: {held}")

    joint_windows = _read_csv(output / "count_mark_joint_window_scores.csv",
                              "count-mark joint window scores")
    _require(joint_windows, WINDOW_KEY + ["scene_id", "outer_held_out_scene_id",
                                           "stage2_mpc_count", "count_log_score",
                                           "mark_component_log_score", "mark_component_status",
                                           "joint_product_log_score", "status"],
             "count-mark joint window scores")
    joint_keys = _keys(joint_windows, WINDOW_KEY, "count-mark joint window scores")
    if set(map(tuple, joint_keys.itertuples(index=False, name=None))) != window_key_set:
        raise ValueError("count-mark joint scores omit or add a Stage2-selected window")
    if len(joint_windows) != len(window_keys):
        raise ValueError("count-mark joint scores must retain every selected window exactly once")
    joint_by_key = joint_windows.set_index(WINDOW_KEY)
    count_by_key = count.set_index(WINDOW_KEY)
    mark_by_key = mark_windows.set_index(WINDOW_KEY)
    for identity in window_key_set:
        row = joint_by_key.loc[identity]
        source_scene = scene_by_window[identity]
        if (str(row.scene_id) != source_scene or str(row.outer_held_out_scene_id) != source_scene):
            raise ValueError("count-mark joint held-out identity differs from selected-window scene")
        expected_n = expected_counts[identity]
        if int(row.stage2_mpc_count) != expected_n:
            raise ValueError("count-mark joint score changed the source Stage2 count")
        count_row = count_by_key.loc[identity]
        count_supported = str(count_row.status) == "SCORED" and np.isfinite(float(count_row.log_score))
        if count_supported:
            if not np.isclose(float(row.count_log_score), float(count_row.log_score), rtol=1e-12, atol=1e-12):
                raise ValueError("count-mark joint count term differs from held-out count score")
        elif pd.notna(row.count_log_score):
            raise ValueError("unscorable count term must not be assigned a joint score")
        if expected_n == 0:
            if (str(row.mark_component_status) != "EMPTY_MARK_SET"
                    or not np.isclose(float(row.mark_component_log_score), 0.0, rtol=0, atol=0)):
                raise ValueError("zero-MPC selected window must have an empty mark term of zero")
            mark_supported = True
            mark_value = 0.0
        else:
            mark_row = mark_by_key.loc[identity]
            product_status = str(mark_row.product_score_status)
            mark_value = pd.to_numeric(pd.Series([mark_row.product_marginal_log_score]),
                                       errors="coerce").iloc[0]
            mark_supported = product_status == "SCORED" and np.isfinite(mark_value)
            if mark_supported:
                if (str(row.mark_component_status) != "SCORED"
                        or not np.isclose(float(row.mark_component_log_score), float(mark_value),
                                          rtol=1e-12, atol=1e-12)):
                    raise ValueError("count-mark joint mark term differs from product-marginal window score")
            elif str(row.mark_component_status) != "UNSCORABLE_MARK_SCORE" or pd.notna(
                    row.mark_component_log_score):
                raise ValueError("unscorable product-mark term is not retained as unscorable")
        expected_status = ("SCORED" if count_supported and mark_supported else
                           "UNSUPPORTED_COUNT_CATEGORY" if str(count_row.status) == "UNSUPPORTED_COUNT_CATEGORY"
                           else "UNSCORABLE_COUNT_SCORE" if not count_supported
                           else "UNSCORABLE_MARK_SCORE")
        if str(row.status) != expected_status:
            raise ValueError("count-mark joint score status disagrees with its components")
        if expected_status == "SCORED":
            expected_joint = float(count_row.log_score) + float(mark_value)
            if not np.isclose(float(row.joint_product_log_score), expected_joint, rtol=1e-12, atol=1e-12):
                raise ValueError("factorized joint score is not count log score plus product-mark score")
        elif pd.notna(row.joint_product_log_score):
            raise ValueError("unscorable factorized joint row must not have a finite score")

    joint_scenes = _read_csv(output / "count_mark_joint_scene_scores.csv",
                             "count-mark joint scene scores")
    _require(joint_scenes, ["scene_id", "window_n", "scored_window_n", "unscorable_window_n",
                            "status", "joint_product_mean_log_score"],
             "count-mark joint scene scores")
    if joint_scenes.scene_id.astype(str).duplicated().any() or set(joint_scenes.scene_id.astype(str)) != all_scenes:
        raise ValueError("count-mark joint scene scores do not cover each selected-window scene exactly once")
    for scene in all_scenes:
        window_rows = joint_windows.loc[joint_windows.scene_id.astype(str).eq(scene)]
        scene_row = joint_scenes.loc[joint_scenes.scene_id.astype(str).eq(scene)].iloc[0]
        scored = window_rows.status.astype(str).eq("SCORED")
        if (int(scene_row.window_n) != len(window_rows)
                or int(scene_row.scored_window_n) != int(scored.sum())
                or int(scene_row.unscorable_window_n) != int((~scored).sum())):
            raise ValueError(f"count-mark joint scene support differs from its windows: {scene}")
        scene_status = "SCORED" if scored.all() else (
            "UNSUPPORTED_COUNT_CATEGORY" if window_rows.status.astype(str).eq("UNSUPPORTED_COUNT_CATEGORY").any()
            else "UNSCORABLE_COUNT_SCORE" if window_rows.status.astype(str).eq("UNSCORABLE_COUNT_SCORE").any()
            else "UNSCORABLE_MARK_SCORE")
        if str(scene_row.status) != scene_status:
            raise ValueError(f"count-mark joint scene status differs from its window scores: {scene}")
        if scored.all():
            expected_mean = float(pd.to_numeric(window_rows.joint_product_log_score, errors="raise").mean())
            if not np.isclose(float(scene_row.joint_product_mean_log_score), expected_mean,
                              rtol=1e-12, atol=1e-12):
                raise ValueError(f"count-mark joint scene mean mismatch: {scene}")
        elif pd.notna(scene_row.joint_product_mean_log_score):
            raise ValueError(f"unscorable count-mark scene must not report a complete mean score: {scene}")
    joint_macro = float(pd.to_numeric(
        joint_scenes.loc[joint_scenes.status.astype(str).eq("SCORED"),
                         "joint_product_mean_log_score"], errors="raise").mean()) if (
                             joint_scenes.status.astype(str).eq("SCORED").any()) else None
    if summary.get("count_mark_joint_scene_macro_mean_log_score") is None:
        if joint_macro is not None:
            raise ValueError("summary omits count-mark joint scene macro score")
    elif joint_macro is None or not np.isclose(
            float(summary["count_mark_joint_scene_macro_mean_log_score"]), joint_macro,
            rtol=1e-12, atol=1e-12):
        raise ValueError("summary count-mark joint scene macro score mismatch")
    if int(summary.get("count_mark_joint_scorable_scene_n", -1)) != int(
            joint_scenes.status.astype(str).eq("SCORED").sum()):
        raise ValueError("summary count-mark joint scorable scene count mismatch")
    if int(summary.get("count_mark_joint_unscorable_window_n", -1)) != int(
            joint_windows.status.astype(str).ne("SCORED").sum()):
        raise ValueError("summary count-mark joint unscorable-window count mismatch")

    folds = _read_csv(output / "mark_folds.csv", "mark folds")
    _require(folds, ["held_out_scene_id", "training_scene_ids", "test_window_n", "test_mpc_n", "fit_status"],
             "mark folds")
    if set(folds.held_out_scene_id.astype(str)) != mark_scenes or folds.held_out_scene_id.duplicated().any():
        raise ValueError("mark fold table does not contain exactly one row per MPC-bearing scene")
    scene_window_n = mpcs.groupby("scene_id")[WINDOW_KEY].apply(lambda keys: keys.drop_duplicates().shape[0]).to_dict()
    scene_mpc_n = mpcs.groupby("scene_id").size().to_dict()
    for row in folds.itertuples(index=False):
        held = str(row.held_out_scene_id)
        if _parse_string_list(row.training_scene_ids, "mark_folds.training_scene_ids") != mark_scenes - {held}:
            raise ValueError(f"mark fold training scene leakage or omission: {held}")
        if int(row.test_window_n) != int(scene_window_n[held]) or int(row.test_mpc_n) != int(scene_mpc_n.get(held, 0)):
            raise ValueError(f"mark fold test support mismatch: {held}")

    parameters = _read_csv(output / "mark_parameters.csv", "mark parameters")
    _require(parameters, ["outer_held_out_scene_id", "variable", "selected_family", "fit_status",
                          "parameters_json", "training_scene_ids"], "mark parameters")
    if parameters.duplicated(["outer_held_out_scene_id", "variable"]).any():
        raise ValueError("duplicate held-out mark parameter record")
    for row in parameters.itertuples(index=False):
        held = str(row.outer_held_out_scene_id)
        if held not in mark_scenes:
            raise ValueError("mark parameter has unknown held-out scene")
        if _parse_string_list(row.training_scene_ids, "mark_parameters.training_scene_ids") != mark_scenes - {held}:
            raise ValueError(f"mark parameter fit includes held-out scene {held}")
        try:
            params = json.loads(str(row.parameters_json))
        except json.JSONDecodeError as exc:
            raise ValueError("mark parameters_json is malformed") from exc
        if row.fit_status == "PASS":
            if not isinstance(params, dict) or not params:
                raise ValueError("PASS mark fit has no parameter object")
            numeric = [value for value in params.values() if isinstance(value, (int, float))]
            if not numeric or not np.isfinite(np.asarray(numeric, dtype=float)).all():
                raise ValueError("PASS mark fit contains missing or nonfinite parameters")

    inner_scores = _read_csv(output / "mark_inner_family_scores.csv", "nested inner-family scores")
    failures = _read_csv(output / "mark_failures.csv", "nested mark failures")
    diagnostic_columns = ["outer_held_out_scene_id", "variable", "family", "outer_training_scenes",
                          "inner_held_out_scene_id", "inner_training_scene_ids", "training_window_n",
                          "test_window_n", "fit_status", "score_status", "mean_window_log_score",
                          "failure_reason", "boundary_parameters"]
    _require(inner_scores, diagnostic_columns, "nested inner-family scores")
    _require(failures, diagnostic_columns, "nested mark failures")
    failure_key = ["outer_held_out_scene_id", "variable", "family", "inner_held_out_scene_id"]
    for label, table in (("nested inner-family scores", inner_scores), ("nested mark failures", failures)):
        _keys(table, failure_key, label)
        if not table.variable.astype(str).isin(MARK_COLUMNS).all():
            raise ValueError(f"{label} contains an unknown mark variable")
        if not table.outer_held_out_scene_id.astype(str).isin(mark_scenes).all():
            raise ValueError(f"{label} contains an unknown outer held-out scene")
    expected_failures = inner_scores.loc[inner_scores.score_status.astype(str).ne("PASS")].copy()
    if list(failures.columns) != list(inner_scores.columns):
        raise ValueError("nested failure table schema differs from inner-family score table")
    expected_failures = expected_failures.sort_values(failure_key).reset_index(drop=True)
    actual_failures = failures.sort_values(failure_key).reset_index(drop=True)
    if len(actual_failures) != len(expected_failures):
        raise ValueError("nested failure table omits or adds non-PASS inner-family diagnostics")
    for column in diagnostic_columns:
        if column in {"training_window_n", "test_window_n", "mean_window_log_score"}:
            expected_values = pd.to_numeric(expected_failures[column], errors="coerce").to_numpy(float)
            actual_values = pd.to_numeric(actual_failures[column], errors="coerce").to_numpy(float)
            equal = np.isclose(expected_values, actual_values, rtol=0, atol=0, equal_nan=True)
        else:
            expected_values = expected_failures[column].astype("string").fillna("<NA>").to_numpy()
            actual_values = actual_failures[column].astype("string").fillna("<NA>").to_numpy()
            equal = expected_values == actual_values
        if not np.asarray(equal).all():
            raise ValueError(f"nested failure table does not match its inner score evidence: {column}")
    if int(summary.get("mark_failure_record_n", -1)) != len(actual_failures):
        raise ValueError("summary nested mark-failure count does not reconcile")

    tails = _read_csv(output / "mark_tails.csv", "held-out mark-tail diagnostics")
    tail_columns = ["outer_held_out_scene_id", "variable", "family", "quantile",
                    "training_predicted_quantile", "heldout_empirical_quantile",
                    "quantile_difference_predicted_minus_empirical",
                    "heldout_coverage_at_predicted_quantile", "expected_tail_support_n",
                    "heldout_n", "status", "training_fit_used", "uncertainty_claim"]
    _require(tails, tail_columns, "held-out mark-tail diagnostics")
    tail_key = ["outer_held_out_scene_id", "variable", "quantile"]
    tail_keys = _keys(tails, tail_key, "held-out mark-tail diagnostics")
    # ``DataFrame.quantile`` is a method, so use explicit column indexing here.
    quantile_values = pd.to_numeric(tail_keys["quantile"], errors="coerce")
    if not set(quantile_values.astype(float)).issubset(set(TAIL_QUANTILES)):
        raise ValueError("mark-tail diagnostics contain an unknown quantile")
    expected_tail_keys = {(scene, variable, float(q)) for scene in mark_scenes
                          for variable in MARK_COLUMNS for q in TAIL_QUANTILES}
    actual_tail_keys = set((str(row.outer_held_out_scene_id), str(row.variable), float(row.quantile))
                           for row in tails.itertuples(index=False))
    if actual_tail_keys != expected_tail_keys or len(tails) != len(expected_tail_keys):
        raise ValueError("mark-tail diagnostics omit or add outer-scene/variable/quantile records")
    parameter_lookup = parameters.set_index(["outer_held_out_scene_id", "variable"])
    mpc_n_by_scene = mpcs.groupby("scene_id").size().to_dict()
    for row in tails.itertuples(index=False):
        scene, variable, quantile = str(row.outer_held_out_scene_id), str(row.variable), float(row.quantile)
        parameter = parameter_lookup.loc[(scene, variable)]
        if str(row.family) != str(parameter.selected_family):
            raise ValueError("mark-tail family does not match its outer-training parameter fit")
        heldout_n = int(mpc_n_by_scene[scene])
        support = float(heldout_n * min(quantile, 1.0 - quantile))
        if int(row.heldout_n) != heldout_n or not np.isclose(
                float(row.expected_tail_support_n), support, rtol=1e-12, atol=1e-12):
            raise ValueError("mark-tail held-out or expected tail-support count mismatch")
        fit_available = str(parameter.fit_status) == "PASS"
        expected_tail_status = ("LOW_SUPPORT" if support < 10.0 else "DESCRIPTIVE_DIAGNOSTIC") \
            if fit_available else "FIT_UNAVAILABLE"
        if str(row.status) != expected_tail_status:
            raise ValueError("mark-tail status does not match fit availability and support threshold")
        training_fit_used = str(row.training_fit_used).strip().lower() in {"true", "1"}
        if fit_available:
            if not training_fit_used:
                raise ValueError("mark-tail record does not attest use of the outer-training fit")
            for column in ("training_predicted_quantile", "heldout_empirical_quantile",
                           "quantile_difference_predicted_minus_empirical",
                           "heldout_coverage_at_predicted_quantile"):
                if not np.isfinite(float(getattr(row, column))):
                    raise ValueError(f"mark-tail {column} is nonfinite")
            if not np.isclose(float(row.quantile_difference_predicted_minus_empirical),
                              float(row.training_predicted_quantile) - float(row.heldout_empirical_quantile),
                              rtol=1e-12, atol=1e-12):
                raise ValueError("mark-tail predicted-minus-empirical quantile difference mismatch")
            if not 0.0 <= float(row.heldout_coverage_at_predicted_quantile) <= 1.0:
                raise ValueError("mark-tail empirical coverage must be within [0,1]")
    low_support_n = int(tails.status.astype(str).eq("LOW_SUPPORT").sum())
    if int(summary.get("mark_low_support_tail_record_n", -1)) != low_support_n:
        raise ValueError("summary low-support tail count does not reconcile")

    pdp = _read_csv(output / "pdp_window_predictions.csv", "PDP window predictions")
    _require(pdp, WINDOW_KEY + ["scene_id", "outer_held_out_scene_id", "target", "observed",
                                 "pdp_peak_at_grid_boundary", "stage2_mpc_count", "training_scene_ids",
                                 "predictor_value", "baseline_training_mean", "baseline_prediction",
                                 "linear_intercept", "linear_slope", "linear_prediction"],
             "PDP window predictions")
    if not set(pdp.target.astype(str)).issubset(set(PDP_TARGETS)):
        raise ValueError("PDP predictions contain an unknown target")
    prediction_keys = WINDOW_KEY + ["target"]
    pdp_key_frame = _keys(pdp, prediction_keys, "PDP predictions")
    expected_pdp_keys = {(run, win, target) for run, win in window_key_set for target in PDP_TARGETS}
    if set(map(tuple, pdp_key_frame.itertuples(index=False, name=None))) != expected_pdp_keys:
        raise ValueError("PDP predictions omit or add window/target identities")
    predictor_by_target = {
        "pdp_rms_width_code_delay_samples": "sage_relative_power_delay_rms_samples",
        "pdp_peak_minus_sage_direct_delay_samples": "sage_relative_power_delay_centroid_samples",
    }
    recomputed_by_key = recomputed.set_index(WINDOW_KEY)
    features_by_key = features.set_index(WINDOW_KEY)
    for held in all_scenes:
        training_mask = scenes.astype("string").str.strip().ne(held).to_numpy()
        for target, predictor in predictor_by_target.items():
            train_features = features.loc[training_mask]
            train_predictors = recomputed.loc[training_mask, predictor].to_numpy(float)
            train_y = pd.to_numeric(train_features[target], errors="raise").to_numpy(float)
            baseline = float(np.mean(train_y))
            design = np.column_stack((np.ones(len(train_predictors)), train_predictors))
            coefficients, _, rank, _ = np.linalg.lstsq(design, train_y, rcond=None)
            linear_identifiable = len(train_y) >= 2 and rank == 2 and np.isfinite(coefficients).all()
            fold_predictions = pdp.loc[pdp.outer_held_out_scene_id.astype(str).eq(held)
                                       & pdp.target.astype(str).eq(target)]
            for prediction in fold_predictions.itertuples(index=False):
                identity = (str(prediction.run_id), str(prediction.window_id))
                expected_predictor = float(recomputed_by_key.loc[identity, predictor])
                expected_observed = float(features_by_key.loc[identity, target])
                if not np.isclose(float(prediction.predictor_value), expected_predictor, rtol=1e-12, atol=1e-12):
                    raise ValueError("PDP predictor differs from independently recomputed SAGE summary")
                if not np.isclose(float(prediction.observed), expected_observed, rtol=1e-12, atol=1e-12):
                    raise ValueError("PDP held-out observed value differs from frozen source")
                if not np.isclose(float(prediction.baseline_training_mean), baseline, rtol=1e-12, atol=1e-12):
                    raise ValueError(f"PDP baseline used non-training or incorrect observations for {held}")
                if not np.isclose(float(prediction.baseline_prediction), baseline, rtol=1e-12, atol=1e-12):
                    raise ValueError("PDP intercept prediction does not match training-only mean")
                if linear_identifiable:
                    predicted = float(coefficients[0] + coefficients[1] * expected_predictor)
                    if not np.isclose(float(prediction.linear_intercept), float(coefficients[0]), rtol=1e-10, atol=1e-10):
                        raise ValueError("PDP linear intercept does not match independent training fit")
                    if not np.isclose(float(prediction.linear_slope), float(coefficients[1]), rtol=1e-10, atol=1e-10):
                        raise ValueError("PDP linear slope does not match independent training fit")
                    if not np.isclose(float(prediction.linear_prediction), predicted, rtol=1e-10, atol=1e-10):
                        raise ValueError("PDP linear prediction does not match independent training fit")
                elif pd.notna(prediction.linear_prediction):
                    raise ValueError("unidentifiable PDP linear model has a numeric prediction")
    for row in pdp.itertuples(index=False):
        identity = (str(row.run_id), str(row.window_id))
        scene = scene_by_window[identity]
        if str(row.scene_id) != scene or str(row.outer_held_out_scene_id) != scene:
            raise ValueError("PDP held-out fold does not match source scene identity")
        training = _parse_string_list(row.training_scene_ids, "PDP training_scene_ids")
        if training != all_scenes - {scene}:
            raise ValueError("PDP prediction training scenes contain leakage or omission")
        if int(row.stage2_mpc_count) != expected_counts[identity]:
            raise ValueError("PDP prediction changed source selected-window count")
        source_boundary = features.loc[(features.run_id.astype(str).eq(identity[0]))
                                       & (features.window_id.astype(str).eq(identity[1])),
                                       "pdp_peak_at_grid_boundary"].iloc[0]
        source_boundary = str(source_boundary).strip().lower() in {"true", "1"}
        row_boundary = str(row.pdp_peak_at_grid_boundary).strip().lower() in {"true", "1"}
        if row_boundary != source_boundary:
            raise ValueError("PDP prediction changed a frozen boundary-peak flag")
        if not pd.notna(row.observed):
            raise ValueError("PDP held-out response must remain present in this frozen population")

    pdp_scores = _read_csv(output / "pdp_scene_scores.csv", "PDP scene scores")
    score_key = ["outer_held_out_scene_id", "scene_id", "target", "model"]
    _require(pdp_scores, score_key + ["window_n", "scored_window_n",
                                      "missing_or_unscorable_window_n", "boundary_peak_window_n",
                                      "status", "mae", "rmse", "training_scene_ids",
                                      "training_window_n"], "PDP scene scores")
    score_keys = _keys(pdp_scores, score_key, "PDP scene scores")
    expected_score_keys = {
        (scene, scene, target, model)
        for scene in all_scenes for target in PDP_TARGETS
        for model in ("INTERCEPT", "LINEAR")
    }
    if set(map(tuple, score_keys.itertuples(index=False, name=None))) != expected_score_keys:
        raise ValueError("PDP scene scores omit or add a held-out scene/model/target")
    if pdp_scores.duplicated(score_key).any():
        raise ValueError("duplicate PDP scene score identity")
    prediction_columns = {"INTERCEPT": "baseline_prediction", "LINEAR": "linear_prediction"}
    fit_status_columns = {"INTERCEPT": "baseline_fit_status", "LINEAR": "linear_fit_status"}
    for row in pdp_scores.itertuples(index=False):
        held = str(row.outer_held_out_scene_id)
        if str(row.scene_id) != held:
            raise ValueError("PDP scene score identity differs from its held-out scene")
        target = str(row.target)
        model = str(row.model)
        if target not in PDP_TARGETS or model not in prediction_columns:
            raise ValueError("PDP scene score contains an unknown target or model")
        training = _parse_string_list(row.training_scene_ids, "PDP score training_scene_ids")
        if training != all_scenes - {held}:
            raise ValueError("PDP scene score training scenes contain leakage or omission")
        if int(row.training_window_n) != int((scenes.astype("string").str.strip() != held).sum()):
            raise ValueError("PDP scene score training window support mismatch")
        fold = pdp.loc[pdp.outer_held_out_scene_id.astype(str).eq(held)
                       & pdp.target.astype(str).eq(target)]
        if len(fold) != int(row.window_n):
            raise ValueError("PDP scene score window support differs from its predictions")
        predicted = pd.to_numeric(fold[prediction_columns[model]], errors="coerce").to_numpy(float)
        observed = pd.to_numeric(fold.observed, errors="coerce").to_numpy(float)
        valid = np.isfinite(predicted) & np.isfinite(observed)
        if int(row.scored_window_n) != int(valid.sum()) or int(row.missing_or_unscorable_window_n) != int(len(fold) - valid.sum()):
            raise ValueError("PDP scene score scored/unscorable support differs from its predictions")
        boundary_flags = fold.pdp_peak_at_grid_boundary.astype(str).str.strip().str.lower().isin(
            {"true", "1"})
        if int(row.boundary_peak_window_n) != int(boundary_flags.sum()):
            raise ValueError("PDP scene score boundary support differs from its predictions")
        if valid.any():
            if str(row.status) != "SCORED":
                raise ValueError("PDP scene score status disagrees with finite predictions")
            residual = predicted[valid] - observed[valid]
            expected_mae = float(np.mean(np.abs(residual)))
            expected_rmse = float(np.sqrt(np.mean(residual ** 2)))
            if not np.isclose(float(row.mae), expected_mae, rtol=1e-12, atol=1e-12) or not np.isclose(
                    float(row.rmse), expected_rmse, rtol=1e-12, atol=1e-12):
                raise ValueError("PDP scene score mismatch with window predictions")
        elif str(row.status) != "NO_SCORABLE_HELDOUT_RESPONSE":
            raise ValueError("unscorable PDP scene score has an unexpected status")

    # The summary is a convenience aggregate; independently reconcile it when present.
    summary_pdp = summary.get("pdp_scene_scores")
    if summary_pdp is not None:
        for target in PDP_TARGETS:
            if target not in summary_pdp:
                raise ValueError(f"summary omits PDP scene scores for {target}")
            for model in prediction_columns:
                records = pdp_scores.loc[pdp_scores.target.astype(str).eq(target)
                                          & pdp_scores.model.astype(str).eq(model)
                                          & pdp_scores.status.astype(str).eq("SCORED")]
                if records.empty:
                    raise ValueError(f"no scored PDP scenes to reconcile for {target}/{model}")
                recorded = summary_pdp[target].get(model)
                if not isinstance(recorded, dict):
                    raise ValueError(f"summary PDP scene score is malformed for {target}/{model}")
                expected_macro_mae = float(pd.to_numeric(records.mae, errors="raise").mean())
                expected_macro_rmse = float(pd.to_numeric(records.rmse, errors="raise").mean())
                if int(recorded.get("scored_scene_n", -1)) != len(records) or not np.isclose(
                        float(recorded.get("scene_macro_mae", np.nan)), expected_macro_mae,
                        rtol=1e-12, atol=1e-12) or not np.isclose(
                        float(recorded.get("scene_macro_rmse", np.nan)), expected_macro_rmse,
                        rtol=1e-12, atol=1e-12):
                    raise ValueError(f"summary PDP scene score mismatch for {target}/{model}")
        for target in PDP_TARGETS:
            baseline = summary_pdp[target]["INTERCEPT"]["scene_macro_rmse"]
            linear = summary_pdp[target]["LINEAR"]["scene_macro_rmse"]
            if not np.isclose(float(summary_pdp[target].get("linear_minus_intercept_rmse", np.nan)),
                              float(linear) - float(baseline), rtol=1e-12, atol=1e-12):
                raise ValueError(f"summary PDP RMSE delta mismatch for {target}")
    boundary = pd.to_numeric(features["pdp_peak_at_grid_boundary"], errors="coerce")
    if boundary.isna().any():
        boundary = features["pdp_peak_at_grid_boundary"].astype(str).str.lower().map(
            {"true": 1, "false": 0, "1": 1, "0": 0})
    boundary_n = int(pd.to_numeric(boundary, errors="raise").sum())
    if "boundary_peak_window_n" in summary and int(summary["boundary_peak_window_n"]) != boundary_n:
        raise ValueError("boundary peak count differs from frozen feature input")

    return {
        "status": "PASS_WITH_LIMITATIONS",
        "output_path": str(output.resolve()),
        "window_n": int(len(window_keys)), "mpc_n": int(len(path_keys)),
        "scene_n": int(len(all_scenes)), "mpc_bearing_window_n": int(len(mark_window_keys)),
        "zero_mpc_selected_window_n": int((np.rint(_as_numeric(features, "stage2_mpc_count", "features")) == 0).sum()),
        "boundary_peak_window_n": boundary_n,
        "count_mark_joint_scene_macro_mean_log_score": joint_macro,
        "count_mark_joint_scorable_scene_n": int(joint_scenes.status.astype(str).eq("SCORED").sum()),
        "count_mark_joint_unscorable_window_n": int(joint_windows.status.astype(str).ne("SCORED").sum()),
        "mark_failure_record_n": int(len(actual_failures)),
        "mark_low_support_tail_record_n": low_support_n,
        "max_recomputed_delay_summary_abs_error": max_delay_error,
        "source_sha256": {"features": _sha256(features_path), "mpcs": _sha256(mpc_path)},
        "code_file_n": len(manifest["code_files"]),
        "validator_sha256": _sha256(Path(__file__).resolve()),
        "validation_scope": "independent key/count/fold, count-mark joint score, retained nested-fit failures and mark-tail support, per-scene PDP score and summary, and direct-plus-MPC delay arithmetic checks; distribution-family and Copula method interpretation remains human review",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--mpcs", type=Path, required=True)
    args = parser.parse_args(argv)
    result = validate_result_package(args.output_dir, args.features, args.mpcs)
    destination = args.output_dir / "independent_validation.json"
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
