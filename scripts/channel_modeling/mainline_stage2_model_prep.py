"""Pure-data preparation helpers for the Mainline Stage2 model.

These functions consume already materialized ledger rows and verified index
metadata. They do not access project files, MATLAB, SAGE, raw IQ, MAT, or HDF5.
They prepare population counts, scene-blocked folds, and CIR association tags;
they do not fit or validate a scientific model.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _required_identity(value: Any, label: str, *, allow_integer: bool = False) -> str:
    if allow_integer and isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise ValueError(f"{label} must be a non-negative identifier")
        return str(value)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty, whitespace-stable string")
    return value


def _window_identity(value: Any, label: str) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        if value > 0:
            return str(value)
    elif isinstance(value, str) and value.isascii() and value.isdecimal():
        numeric_value = int(value)
        if numeric_value > 0 and str(numeric_value) == value:
            return value
    raise ValueError(f"{label} must be a positive canonical decimal window_id")


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value and value.isdecimal():
        result = int(value)
    else:
        raise ValueError(f"{label} must be a positive integer")
    if result <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return result


def _binary_flag(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value in {"0", "1"}:
        return value == "1"
    raise ValueError(f"{label} must be binary 0/1")


def _row_identity(row: Mapping[str, Any], label: str) -> tuple[str, str, int]:
    if not isinstance(row, Mapping):
        raise ValueError(f"{label} must be a mapping row")
    run_id = _required_identity(row.get("run_id"), f"{label}.run_id")
    window_id = _window_identity(row.get("window_id"), f"{label}.window_id")
    path_id = _positive_integer(row.get("path_id"), f"{label}.path_id")
    return run_id, window_id, path_id


def mpc_counts_by_selected_window(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], int]:
    """Count MPC paths for Stage2-represented windows only.

    The input must contain the full selected path set for each represented
    window, including its direct path (path_id 1). An unrepresented Stage0
    window is never synthesized as a zero-count observation.
    """

    counts: dict[tuple[str, str], int] = {}
    path_ids_by_window: dict[tuple[str, str], set[int]] = defaultdict(set)
    seen_paths: set[tuple[str, str, int]] = set()

    for row_number, row in enumerate(rows, start=1):
        run_id, window_id, path_id = _row_identity(row, f"row {row_number}")
        key = (run_id, window_id)
        identity = (run_id, window_id, path_id)
        if identity in seen_paths:
            raise ValueError(f"duplicate Stage2 path identity {identity!r}")
        seen_paths.add(identity)

        is_multipath = _binary_flag(row.get("is_multipath"), f"row {row_number}.is_multipath")
        if (path_id == 1 and is_multipath) or (path_id > 1 and not is_multipath):
            raise ValueError(f"row {row_number}: direct/multipath classification conflicts with path_id")

        counts.setdefault(key, 0)
        path_ids_by_window[key].add(path_id)
        counts[key] += int(is_multipath)

    for key, path_ids in path_ids_by_window.items():
        expected = set(range(1, max(path_ids) + 1))
        if path_ids != expected:
            raise ValueError(f"window {key!r} path IDs are not contiguous from the direct path")

    return counts


def leave_one_scene_out_folds(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build deterministic LOSO folds, keeping all rows from a scene together."""

    indices_by_scene: dict[str, list[int]] = defaultdict(list)
    scene_by_run: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"row {index + 1} must be a mapping row")
        run_id = _required_identity(row.get("run_id"), f"row {index + 1}.run_id")
        scene_id = _required_identity(row.get("scene_id"), f"row {index + 1}.scene_id")
        prior_scene = scene_by_run.setdefault(run_id, scene_id)
        if prior_scene != scene_id:
            raise ValueError(f"run_id {run_id!r} has multiple scene_id labels")
        indices_by_scene[scene_id].append(index)

    ordered_scenes = sorted(indices_by_scene)
    if len(ordered_scenes) < 2:
        raise ValueError("leave-one-scene-out requires at least two scenes")

    folds: list[dict[str, Any]] = []
    for held_out_scene_id in ordered_scenes:
        test_indices = indices_by_scene[held_out_scene_id].copy()
        test_set = set(test_indices)
        train_indices = [index for index in range(len(rows)) if index not in test_set]
        folds.append(
            {
                "held_out_scene_id": held_out_scene_id,
                "train_indices": train_indices,
                "test_indices": test_indices,
            }
        )
    return folds


def _window_id_sequence(value: Any, label: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{label} must be an ordered window-ID sequence")
    result = tuple(
        _window_identity(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    )
    if not result:
        raise ValueError(f"{label} must not be empty for a PASS run")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} contains duplicate window IDs")
    return result


def build_validated_cir_window_index(
    run_evidence: Iterable[Mapping[str, Any]],
) -> tuple[set[str], set[tuple[str, str]]]:
    """Build exact window keys only from PASS receipt/HDF5/index evidence.

    Evidence records require expected, receipt, and HDF5 `run_id` bindings,
    task receipt and HDF5 read-back PASS statuses, and ordered Stage0/PDP
    window-ID sequences. Runs without both PASS statuses remain unvalidated.
    A claimed PASS with mismatched identities or an incomplete, duplicate,
    or nonmatching Stage0/PDP sequence fails closed.
    """

    validated_runs: set[str] = set()
    validated_window_keys: set[tuple[str, str]] = set()
    seen_runs: set[str] = set()

    for record_number, record in enumerate(run_evidence, start=1):
        if not isinstance(record, Mapping):
            raise ValueError(f"run evidence {record_number} must be a mapping")
        run_id = _required_identity(record.get("run_id"), f"run evidence {record_number}.run_id")
        if run_id in seen_runs:
            raise ValueError(f"duplicate run_id evidence {run_id!r}")
        seen_runs.add(run_id)

        receipt_status = record.get("task_receipt_status")
        hdf5_status = record.get("hdf5_readback_status")
        if receipt_status != "PASS" or hdf5_status != "PASS":
            continue

        for field in ("expected_run_id", "task_receipt_run_id", "hdf5_run_id"):
            evidence_run_id = _required_identity(record.get(field), f"{run_id}.{field}")
            if evidence_run_id != run_id:
                raise ValueError(f"{run_id}: {field} run identity does not match expected run identity")

        stage0_ids = _window_id_sequence(
            record.get("stage0_window_ids"), f"{run_id}.stage0_window_ids"
        )
        pdp_ids = _window_id_sequence(record.get("pdp_window_ids"), f"{run_id}.pdp_window_ids")
        if stage0_ids != pdp_ids:
            raise ValueError(f"{run_id}: Stage0 and PDP window ID sequences do not match")

        validated_runs.add(run_id)
        validated_window_keys.update((run_id, window_id) for window_id in stage0_ids)

    return validated_runs, validated_window_keys


def annotate_cir_association(
    rows: Iterable[Mapping[str, Any]],
    validated_runs: Iterable[str],
    validated_window_keys: Iterable[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Copy and tag each Stage2 MPC row without dropping or reordering rows."""

    trusted_runs = {
        _required_identity(run_id, "validated run_id") for run_id in validated_runs
    }
    trusted_window_keys: set[tuple[str, str]] = set()
    for key in validated_window_keys:
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError("validated window keys must be (run_id, window_id) tuples")
        run_id = _required_identity(key[0], "validated window key run_id")
        window_id = _window_identity(key[1], "validated window key window_id")
        if run_id not in trusted_runs:
            raise ValueError(f"window key references a not validated run: {run_id!r}")
        trusted_window_keys.add((run_id, window_id))

    result: list[dict[str, Any]] = []
    seen_paths: set[tuple[str, str, int]] = set()
    for row_number, row in enumerate(rows, start=1):
        run_id, window_id, path_id = _row_identity(row, f"row {row_number}")
        identity = (run_id, window_id, path_id)
        if identity in seen_paths:
            raise ValueError(f"duplicate Stage2 path identity {identity!r}")
        seen_paths.add(identity)
        if "cir_association_status" in row:
            raise ValueError(f"row {row_number} already has cir_association_status")

        window_key = (run_id, window_id)
        if run_id not in trusted_runs:
            status = "UNASSOCIATED"
        elif window_key in trusted_window_keys:
            status = "ASSOCIATED_VALIDATED"
        else:
            status = "NO_CIR_CORRESPONDENCE"

        copied = dict(row)
        copied["cir_association_status"] = status
        result.append(copied)
    return result
