"""Stage3-reliable-evidence Rain effect layer for the darkroom tables.

This module is deliberately independent of MATLAB/SAGE and never reads raw IQ.
It consumes the already audited Rain Stage3 CSV files and transforms an
existing v2.2 canonical table in a new output namespace.  Stage3 rows remain
evidence records; they are not relabeled as Stage4-confirmed paths.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SAMPLE_RATE_HZ = 10_230_000
FINAL_COLUMNS = (
    "ms",
    "SatelliteID",
    "NLOSPathID",
    "RelativeDelay",
    "RelativeDoppler",
    "RelativeAmplitude",
    "RelativePhase_rad",
)
WEATHER_ORDER = ("Clear", "MidRain", "HeavyRain", "RainPooled")
SOURCE_SEMANTICS = "STAGE3_RELIABLE_EVIDENCE"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _as_int(value: Any, field: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer {field}: {value!r}") from exc


def _as_float(value: Any, field: str) -> float:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid float {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite {field}: {value!r}")
    return result


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_stage3_evidence(task_specs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Extract only Stage3 persistent rows linked to reliable centers.

    ``task_specs`` is intentionally explicit.  It is the nine-task frozen
    Rain scope, not a directory glob that could silently admit new tasks.
    """

    result: list[dict[str, Any]] = []
    for spec in task_specs:
        stage3_path = Path(spec["stage3_persistence"])
        reliable_path = Path(spec["stage3_reliable_centers"])
        reliable_rows = _read_csv(reliable_path)
        reliable_ids = {
            _as_int(row["center_window_id"], "center_window_id")
            for row in reliable_rows
            if _as_bool(row.get("reliable_multipath", "1"))
        }
        for row in _read_csv(stage3_path):
            center_id = _as_int(row["center_window_id"], "center_window_id")
            if not _as_bool(row["persistence_pass"]):
                continue
            if center_id not in reliable_ids:
                continue
            delay_samples = _as_float(row["excess_delay_samples"], "excess_delay_samples")
            if delay_samples <= 0:
                raise ValueError(f"Stage3 excess delay must be positive: {stage3_path}:{center_id}")
            path_id = _as_int(row["multipath_id"], "multipath_id")
            if path_id < 1 or path_id > 3:
                raise ValueError(f"unsupported Stage3 NLOS path id: {path_id}")
            result.append(
                {
                    "weather": str(spec["weather"]),
                    "scene_id": str(spec["scene_id"]),
                    "prn": str(spec["prn"]),
                    "tracking_channel": _as_int(spec["tracking_channel"], "tracking_channel"),
                    "task_id": str(spec.get("task_id", f"{spec['scene_id']}__{spec['prn']}__ch{spec['tracking_channel']}")),
                    "center_window_id": center_id,
                    "recording_time_s": _as_float(row["center_recording_time_s"], "center_recording_time_s"),
                    "path_id": path_id,
                    "selected_L": _as_int(row["selected_L"], "selected_L"),
                    "delay_samples": delay_samples,
                    "delay_ns": delay_samples * 1e9 / SAMPLE_RATE_HZ,
                    "doppler_hz": _as_float(row["doppler_offset_hz"], "doppler_offset_hz"),
                    "power_db": _as_float(row["relative_power_db"], "relative_power_db"),
                    "amplitude_ratio": 10.0 ** (_as_float(row["relative_power_db"], "relative_power_db") / 20.0),
                    "matched_window_count": _as_int(row["matched_window_count"], "matched_window_count"),
                    "longest_consecutive_count": _as_int(row["longest_consecutive_count"], "longest_consecutive_count"),
                    "source_stage3_persistence": str(stage3_path),
                    "source_stage3_reliable_centers": str(reliable_path),
                    "source_semantics": SOURCE_SEMANTICS,
                    "gold_labels_used_for_selection": False,
                }
            )
    return result


def build_stage3_episodes(
    evidence: Sequence[Mapping[str, Any]], persistence_radius: int = 2
) -> list[dict[str, Any]]:
    """Attach deterministic overlapping-support episode IDs.

    Reliable centers are connected when their center-window distance is no
    greater than ``2 * persistence_radius``; this is exactly the overlap rule
    for the frozen center +/- radius support intervals.
    """

    by_task: dict[str, list[int]] = defaultdict(list)
    for row in evidence:
        by_task[str(row["task_id"])].append(_as_int(row["center_window_id"], "center_window_id"))
    episode_by_task_center: dict[tuple[str, int], str] = {}
    for task_id, centers in by_task.items():
        previous: int | None = None
        episode_number = 0
        for center in sorted(set(centers)):
            if previous is None or center - previous > 2 * persistence_radius:
                episode_number += 1
            episode_by_task_center[(task_id, center)] = f"{task_id}__episode_{episode_number:04d}"
            previous = center
    output: list[dict[str, Any]] = []
    for row in evidence:
        copy = dict(row)
        copy["episode_id"] = episode_by_task_center[(str(row["task_id"]), _as_int(row["center_window_id"], "center_window_id"))]
        output.append(copy)
    return output


def _weighted_distribution(records: Sequence[Mapping[str, Any]], field: str) -> dict[str, list[float]]:
    if not records:
        raise ValueError(f"no records for distribution {field}")
    values = [(_as_float(row[field], field), float(row["weight"])) for row in records]
    values.sort(key=lambda item: item[0])
    total = sum(weight for _, weight in values)
    if total <= 0:
        raise ValueError(f"non-positive total weight for {field}")
    return {
        "values": [value for value, _ in values],
        "weights": [weight / total for _, weight in values],
    }


def fit_rain_effect_model(evidence: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fit weighted empirical distributions; no Stage4 data is accepted."""

    if not evidence:
        raise ValueError("cannot fit Rain effect model from empty evidence")
    enriched = [dict(row) for row in evidence]
    by_weather: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        if row.get("source_semantics") != SOURCE_SEMANTICS:
            raise ValueError("effect model accepts only Stage3 reliable evidence")
        if row.get("gold_labels_used_for_selection") is not False:
            raise ValueError("gold labels are forbidden in effect model selection")
        by_weather[str(row["weather"])].append(row)
    for weather, records in by_weather.items():
        task_episodes: dict[str, set[str]] = defaultdict(set)
        episode_paths: dict[str, int] = defaultdict(int)
        for row in records:
            task_episodes[str(row["task_id"])].add(str(row["episode_id"]))
            episode_paths[str(row["episode_id"])] += 1
        task_count = len(task_episodes)
        for row in records:
            task_id = str(row["task_id"])
            episode_id = str(row["episode_id"])
            row["weight"] = 1.0 / (task_count * len(task_episodes[task_id]) * episode_paths[episode_id])

    distributions: dict[str, dict[str, dict[str, list[float]]]] = {}
    for weather in ("Clear", "MidRain", "HeavyRain"):
        records = by_weather.get(weather, [])
        if not records:
            raise ValueError(f"missing weather support: {weather}")
        distributions[weather] = {
            "log_delay_ns": _weighted_distribution(
                [{**row, "log_delay_ns": math.log(row["delay_ns"])} for row in records], "log_delay_ns"
            ),
            "doppler_hz": _weighted_distribution(records, "doppler_hz"),
            "power_db": _weighted_distribution(records, "power_db"),
        }
    pooled = by_weather["MidRain"] + by_weather["HeavyRain"]
    distributions["RainPooled"] = {
        "log_delay_ns": _weighted_distribution(
            [{**row, "log_delay_ns": math.log(row["delay_ns"])} for row in pooled], "log_delay_ns"
        ),
        "doppler_hz": _weighted_distribution(pooled, "doppler_hz"),
        "power_db": _weighted_distribution(pooled, "power_db"),
    }
    support_records = dict(by_weather)
    support_records["RainPooled"] = pooled
    return {
        "model_id": "rain-stage3-effect-layer-v1",
        "schema_version": "rain-stage3-effect-layer-schema-1",
        "source_semantics": SOURCE_SEMANTICS,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "persistence_radius": 2,
        "episode_overlap_rule": "center_support_intervals_overlap_when_gap_le_2_radius",
        "distributions": distributions,
        "support": {
            weather: {
                "task_count": len({str(row["task_id"]) for row in support_records.get(weather, [])}),
                "episode_count": len({str(row["episode_id"]) for row in support_records.get(weather, [])}),
                "path_row_count": len(support_records.get(weather, [])),
            }
            for weather in ("Clear", "MidRain", "HeavyRain", "RainPooled")
        },
        "stage4_used_for_fit": False,
        "gold_labels_used_for_selection": False,
        "phase_model": "external_initial_uniform_plus_continuous_doppler_evolution",
        "main_path_policy": "unchanged_by_stage3_rain_layer",
        "nlos_policy": "apply_pooled_rain_transform_to_slots_1_2_3_and_keep_positive",
    }


def _uniform(master_seed: int, *parts: Any) -> float:
    payload = "|".join(str(part) for part in (master_seed, *parts)).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return random.Random(seed).random()


def _quantile(distribution: Any, u: float) -> float:
    if isinstance(distribution, Mapping):
        values = [float(value) for value in distribution["values"]]
        weights = [float(weight) for weight in distribution["weights"]]
    else:
        values = [float(value) for value in distribution]
        weights = [1.0 / len(values)] * len(values)
    if not values:
        raise ValueError("empty distribution")
    target = max(0.0, min(1.0, u))
    cumulative = 0.0
    for value, weight in zip(values, weights):
        cumulative += weight
        if target <= cumulative:
            return value
    return values[-1]


def _model_quantile(model: Mapping[str, Any], weather: str, field: str, u: float) -> float:
    try:
        return _quantile(model["distributions"][weather][field], u)
    except KeyError as exc:
        raise ValueError(f"model lacks distribution {weather}/{field}") from exc


def _wrap_phase(value: float) -> float:
    return (value + math.pi) % (2.0 * math.pi) - math.pi


class _RowTransformer:
    def __init__(self, model: Mapping[str, Any], weather: str, master_seed: int) -> None:
        self.model = model
        self.weather = weather
        self.master_seed = int(master_seed)
        self.states: dict[tuple[str, int], tuple[int, float]] = {}
        self.effect_cache: dict[tuple[str, int, int], tuple[float, float, float]] = {}

    def _effect(self, satellite: str, path_id: int, block: int) -> tuple[float, float, float]:
        key = (satellite, path_id, block)
        cached = self.effect_cache.get(key)
        if cached is not None:
            return cached
        base_u_parts = (self.weather, satellite, path_id, block)
        u_delay = _uniform(self.master_seed, *base_u_parts, "delay")
        u_doppler = _uniform(self.master_seed, *base_u_parts, "doppler")
        u_power = _uniform(self.master_seed, *base_u_parts, "power")
        log_delta = _model_quantile(self.model, self.weather, "log_delay_ns", u_delay) - _model_quantile(self.model, "Clear", "log_delay_ns", u_delay)
        doppler_delta = _model_quantile(self.model, self.weather, "doppler_hz", u_doppler) - _model_quantile(self.model, "Clear", "doppler_hz", u_doppler)
        power_delta = _model_quantile(self.model, self.weather, "power_db", u_power) - _model_quantile(self.model, "Clear", "power_db", u_power)
        cached = (log_delta, doppler_delta, power_delta)
        self.effect_cache[key] = cached
        return cached

    def transform(self, row: Mapping[str, Any]) -> dict[str, Any]:
        ms = _as_int(row["ms"], "ms")
        satellite = str(row["SatelliteID"])
        path_id = _as_int(row["NLOSPathID"], "NLOSPathID")
        delay = _as_float(row["RelativeDelay"], "RelativeDelay")
        doppler = _as_float(row["RelativeDoppler"], "RelativeDoppler")
        amplitude = _as_float(row["RelativeAmplitude"], "RelativeAmplitude")
        input_phase = _as_float(row["RelativePhase_rad"], "RelativePhase_rad")
        if path_id == 0 or self.weather == "Clear":
            new_delay, new_doppler, new_amplitude = delay, doppler, amplitude
        else:
            block = (ms - 1) // 40
            log_delta, doppler_delta, power_delta = self._effect(satellite, path_id, block)
            new_delay = max(1e-12, delay * math.exp(log_delta))
            new_doppler = doppler + doppler_delta
            new_amplitude = amplitude * (10.0 ** (power_delta / 20.0))
            if new_amplitude <= 0 or not math.isfinite(new_amplitude):
                raise ValueError("Rain effect produced invalid NLOS amplitude")

        key = (satellite, path_id)
        previous = self.states.get(key)
        if path_id == 0 or self.weather == "Clear":
            new_phase = input_phase
        elif previous is None or previous[0] != ms - 1:
            new_phase = _wrap_phase(input_phase)
        else:
            new_phase = _wrap_phase(previous[1] + 2.0 * math.pi * new_doppler * 1e-3)
        self.states[key] = (ms, new_phase)
        return {
            "ms": ms,
            "SatelliteID": satellite,
            "NLOSPathID": path_id,
            "RelativeDelay": float(new_delay),
            "RelativeDoppler": float(new_doppler),
            "RelativeAmplitude": float(new_amplitude),
            "RelativePhase_rad": float(new_phase),
        }


def apply_effect_to_rows(
    rows: Sequence[Mapping[str, Any]], model: Mapping[str, Any], *, weather: str, master_seed: int
) -> list[dict[str, Any]]:
    transformer = _RowTransformer(model, weather, master_seed)
    return [transformer.transform(row) for row in rows]


def validate_new_only_namespace(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"new-only output namespace already exists: {path}")


def validate_output_namespace(path: Path) -> None:
    if any(part.lower() == "sage_results" for part in path.parts):
        raise ValueError(f"Rain effect output cannot be written under scenes/**/sage_results: {path}")


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_stage3_evidence(path: Path, evidence: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "weather", "scene_id", "prn", "tracking_channel", "task_id", "center_window_id",
        "recording_time_s", "path_id", "selected_L", "delay_samples", "delay_ns", "doppler_hz",
        "power_db", "amplitude_ratio", "matched_window_count", "longest_consecutive_count",
        "episode_id", "source_stage3_persistence", "source_stage3_reliable_centers", "source_semantics",
        "gold_labels_used_for_selection",
    ]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in evidence:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_episode_catalog(path: Path, evidence: Sequence[Mapping[str, Any]]) -> None:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence:
        groups[str(row["episode_id"])].append(row)
    fields = ["episode_id", "weather", "task_id", "first_center_window_id", "last_center_window_id", "center_count", "path_row_count"]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for episode_id in sorted(groups):
            rows = groups[episode_id]
            centers = sorted({_as_int(row["center_window_id"], "center_window_id") for row in rows})
            writer.writerow({
                "episode_id": episode_id,
                "weather": rows[0]["weather"],
                "task_id": rows[0]["task_id"],
                "first_center_window_id": centers[0],
                "last_center_window_id": centers[-1],
                "center_count": len(centers),
                "path_row_count": len(rows),
            })


def apply_effect_to_file(input_path: Path, output_path: Path, model: Mapping[str, Any], *, weather: str, master_seed: int) -> dict[str, Any]:
    transformer = _RowTransformer(model, weather, master_seed)
    rows = 0
    with input_path.open("r", encoding="utf-8-sig", newline="") as source, output_path.open("x", encoding="utf-8", newline="") as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != FINAL_COLUMNS:
            raise ValueError(f"canonical input columns do not match v2.2 contract: {input_path}")
        writer = csv.DictWriter(target, fieldnames=FINAL_COLUMNS, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in reader:
            writer.writerow(transformer.transform(row))
            rows += 1
    return {"path": str(output_path), "rows": rows, "sha256": sha256_file(output_path)}


def write_collection(
    output_dir: Path,
    *,
    export_manifest_path: Path,
    evidence: Sequence[Mapping[str, Any]],
    model: Mapping[str, Any],
    master_seed: int,
    layer_weather: str = "RainPooled",
    prepared_namespace: bool = False,
) -> dict[str, Any]:
    """Write eight new Rain tables and their provenance into an absent namespace."""

    validate_output_namespace(output_dir)
    if prepared_namespace:
        if not output_dir.is_dir() or any(output_dir.iterdir()):
            raise FileExistsError(f"prepared new-only namespace is not an empty directory: {output_dir}")
    else:
        validate_new_only_namespace(output_dir)
    if layer_weather not in {"RainPooled", "MidRain", "HeavyRain"}:
        raise ValueError(f"unsupported layer weather: {layer_weather}")
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = list(evidence)
    model_path = output_dir / "rain_effect_model.json"
    model_path.write_bytes(_canonical_json(model))
    write_stage3_evidence(output_dir / "stage3_rain_path_evidence.csv", evidence)
    write_episode_catalog(output_dir / "stage3_rain_episode_catalog.csv", evidence)
    exports = json.loads(export_manifest_path.read_text(encoding="utf-8"))["exports"]
    table_records: list[dict[str, Any]] = []
    for export in exports:
        source_path = Path(export["destination_path"])
        if sha256_file(source_path).lower() != str(export["destination_sha256"]).lower():
            raise ValueError(f"base canonical table hash mismatch: {source_path}")
        stem = source_path.stem
        target = output_dir / "tables" / f"{stem}__rain.csv"
        target.parent.mkdir(exist_ok=True)
        table_records.append(apply_effect_to_file(source_path, target, model, weather=layer_weather, master_seed=master_seed))
        table_records[-1].update({"environment_class": export["environment_class"], "quality_mode": export["quality_mode"], "source_path": str(source_path), "source_sha256": export["destination_sha256"]})
    manifest = {
        "schema_version": "rain-effect-layer-collection-1",
        "collection_id": output_dir.name,
        "layer_weather": layer_weather,
        "master_seed": int(master_seed),
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "base_export_manifest": str(export_manifest_path),
        "base_export_manifest_sha256": sha256_file(export_manifest_path),
        "model_file": str(model_path),
        "model_sha256": sha256_file(model_path),
        "evidence_file": str(output_dir / "stage3_rain_path_evidence.csv"),
        "evidence_sha256": sha256_file(output_dir / "stage3_rain_path_evidence.csv"),
        "episode_file": str(output_dir / "stage3_rain_episode_catalog.csv"),
        "episode_sha256": sha256_file(output_dir / "stage3_rain_episode_catalog.csv"),
        "table_count": len(table_records),
        "tables": table_records,
        "final_columns": list(FINAL_COLUMNS),
        "fixed_path_slots": [0, 1, 2, 3],
        "nlos_amplitude_policy": "strictly_positive_preserved",
        "stage4_used_for_fit": False,
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "new_only": True,
        "resume_allowed": False,
    }
    manifest_path = output_dir / "rain_effect_layer_manifest.json"
    manifest_path.write_bytes(_canonical_json(manifest))
    manifest_sha256 = sha256_file(manifest_path)
    (output_dir / "rain_effect_layer_manifest.sha256").write_text(f"{manifest_sha256}  rain_effect_layer_manifest.json\n", encoding="ascii")
    manifest["manifest_sha256"] = manifest_sha256
    return manifest
