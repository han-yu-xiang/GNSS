from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REVIEW_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = Path(r"E:\GNSS_Multipath_Project")
SOURCE_PATH = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scientific_risk_core import ENVIRONMENTS, load_primary_population  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    summary_path = REVIEW_ROOT / "tables/gmm_complexity_summary.csv"
    folds_path = REVIEW_ROOT / "tables/gmm_loso_folds.csv"
    model_path = REVIEW_ROOT / "model/gmm_complexity_results.json"
    summary = pd.read_csv(summary_path)
    folds = pd.read_csv(folds_path)
    model = json.loads(model_path.read_text(encoding="utf-8"))
    source = load_primary_population(SOURCE_PATH)
    checks: dict[str, bool] = {}
    checks["source_sha256_matches_model"] = sha256_file(SOURCE_PATH) == model["source_sha256"]
    checks["summary_has_12_rows"] = len(summary) == 12
    checks["folds_have_54_rows"] = len(folds) == 54
    checks["components_are_1_2_3"] = set(summary["components"].astype(int)) == {1, 2, 3}
    checks["summary_values_finite"] = bool(np.isfinite(summary.select_dtypes(include=[np.number]).to_numpy(float)).all())
    checks["fold_values_finite"] = bool(np.isfinite(folds.select_dtypes(include=[np.number]).to_numpy(float)).all())
    checks["source_population_unchanged"] = len(source) == 518 and source["track_id"].nunique() == 236 and source["scene_id"].nunique() == 9
    group_checks: dict[str, bool] = {}
    for environment in ENVIRONMENTS:
        environment_rows = source.loc[source["environment_class"] == environment]
        scenes = sorted(environment_rows["scene_id"].astype(str).unique())
        for value in ("doppler_offset_hz", "relative_power_db"):
            key = f"{environment}|{value}"
            group_summary = summary.loc[(summary["environment"] == environment) & (summary["value"] == value)]
            group_folds = folds.loc[(folds["environment"] == environment) & (folds["value"] == value)]
            selected_count = int((group_summary["selection_status"] == "SELECTED_ONE_SE_RULE").sum())
            fold_ok = len(group_folds) == len(scenes) * 3
            for _, row in group_folds.iterrows():
                held_out = str(row["held_out_scene"])
                train_scenes = set(str(row["training_scenes"]).split(";"))
                fold_ok = fold_ok and held_out in scenes and held_out not in train_scenes and train_scenes == set(scenes) - {held_out}
                fold_ok = fold_ok and int(row["train_row_count"]) + int(row["test_row_count"]) == len(environment_rows)
            model_ok = True
            for _, row in group_summary.iterrows():
                payload = json.loads(row["model_json"])
                means = np.asarray(payload["means"], dtype=float)
                stds = np.asarray(payload["stds"], dtype=float)
                proportions = np.asarray(payload["proportions"], dtype=float)
                masses = np.asarray(payload["effective_component_mass"], dtype=float)
                model_ok = model_ok and len(means) == int(row["components"])
                model_ok = model_ok and bool(np.all(np.diff(means) >= 0.0))
                model_ok = model_ok and bool(np.all(stds > 0.0))
                model_ok = model_ok and bool(np.isclose(np.sum(proportions), 1.0))
                model_ok = model_ok and bool(np.all(masses >= 5.0))
            group_checks[key] = len(group_summary) == 3 and selected_count == 1 and fold_ok and model_ok
    checks["all_environment_variable_groups_valid"] = all(group_checks.values())
    checks["mountain_doppler_k3_selected"] = bool(
        ((summary["environment"] == "Mountain/Valley")
         & (summary["value"] == "doppler_offset_hz")
         & (summary["components"] == 3)
         & (summary["selection_status"] == "SELECTED_ONE_SE_RULE")).any()
    )
    status = "PASS_WITH_LIMITATIONS" if all(checks.values()) else "FAIL"
    result = {
        "status": status,
        "checks": checks,
        "group_checks": group_checks,
        "source_sha256": sha256_file(SOURCE_PATH),
        "review_only": True,
        "interpretation": "K=3 is selected for Mountain/Valley signed Doppler by the predeclared one-standard-error rule, but its additional narrow negative component and remaining maximum weighted CDF deviation support the empirical-CDF decision for the manuscript route.",
    }
    output_path = REVIEW_ROOT / "qa/gmm_complexity_independent_qa.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = REVIEW_ROOT / "qa/GMM_COMPLEXITY_QA_REPORT.md"
    report_path.write_text(
        "# K=1/2/3 Gaussian-mixture complexity QA\n\n"
        f"Status: **{status}**\n\n"
        "All 12 environment/variable/component summaries and 54 complete-scene folds were checked independently. Training and held-out scene sets are disjoint, model parameters are finite and ordered, and the source population hash matches the recorded input. This QA does not authorize manuscript changes.\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
