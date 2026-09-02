from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.build_main_path_common_gain_fade_model import (
    ensure_new_only_namespace,
    freeze_model_manifest,
    validate_config_contract,
)
from scripts.analysis.channel_modeling.main_path_gain_core import GainFadeConfig


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = PROJECT_ROOT / "configs" / "channel_modeling" / "main_path_common_gain_fade_v1.json"


def test_existing_namespace_is_rejected_without_deleting_existing_artifact(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        ensure_new_only_namespace(tmp_path, output)
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_output_namespace_must_be_under_channel_modeling_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ensure_new_only_namespace(tmp_path, tmp_path / "outside")


def test_config_contract_rejects_changed_policy() -> None:
    config = GainFadeConfig.from_json(CONFIG_PATH)
    validate_config_contract(config)
    changed = config.execution_policy | {"gold_labels_used_for_selection": True}
    with pytest.raises(ValueError):
        validate_config_contract(
            GainFadeConfig(
                model_id=config.model_id,
                model_version=config.model_version,
                sample_rate_hz=config.sample_rate_hz,
                environments=config.environments,
                elevation_bands=config.elevation_bands,
                analysis_bin_ms=config.analysis_bin_ms,
                short_segment_min_duration_s=config.short_segment_min_duration_s,
                baseline_window_s=config.baseline_window_s,
                baseline_quantile=config.baseline_quantile,
                minimum_baseline_points=config.minimum_baseline_points,
                entry_depth_db=config.entry_depth_db,
                entry_sustain_ms=config.entry_sustain_ms,
                exit_depth_db=config.exit_depth_db,
                exit_sustain_ms=config.exit_sustain_ms,
                geometry_tolerance_s=config.geometry_tolerance_s,
                family_tie_tolerance=config.family_tie_tolerance,
                parent_quantile_count=config.parent_quantile_count,
                prior_equivalent_weight=config.prior_equivalent_weight,
                rate_parent_exposure_s=config.rate_parent_exposure_s,
                lag_s=config.lag_s,
                tau_min_s=config.tau_min_s,
                tau_max_s=config.tau_max_s,
                bootstrap_seed=config.bootstrap_seed,
                bootstrap_replicates=config.bootstrap_replicates,
                qa_draw_seed=config.qa_draw_seed,
                qa_draw_count=config.qa_draw_count,
                source=config.source,
                protected_source=config.protected_source,
                execution_policy=changed,
                output_namespace=config.output_namespace,
                marginal_families=config.marginal_families,
            )
        )


def test_manifest_freeze_contains_hashable_policy_and_no_gold_selection(tmp_path: Path) -> None:
    config = GainFadeConfig.from_json(CONFIG_PATH)
    manifest = freeze_model_manifest(
        config,
        config_hash="config-hash",
        source_preflight_hash="source-hash",
        code_hashes={"core": "core-hash"},
        output_hashes={"file.csv": "file-hash"},
    )
    assert manifest["execution_policy"]["gold_labels_used_for_selection"] is False
    assert manifest["config_sha256"] == "config-hash"
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8"))["output_hashes"] == {"file.csv": "file-hash"}
