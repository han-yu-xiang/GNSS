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

from scientific_risk_core import ENVIRONMENTS, load_primary_population, weighted_quantile  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    table_path = REVIEW_ROOT / "tables/signed_doppler_empirical_quantiles.csv"
    model_path = REVIEW_ROOT / "model/signed_doppler_empirical_model.json"
    figure_paths = [REVIEW_ROOT / "figures/signed_doppler_empirical_cdf.png", REVIEW_ROOT / "figures/signed_doppler_empirical_cdf.pdf"]
    source = load_primary_population(SOURCE_PATH)
    table = pd.read_csv(table_path)
    model = json.loads(model_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    checks["source_rows"] = len(source) == 518
    checks["source_sha256_matches_model"] = sha256_file(SOURCE_PATH) == model["source_sha256"]
    checks["environment_rows"] = {
        environment: int((source["environment_class"] == environment).sum()) for environment in ENVIRONMENTS
    } == {"Urban": 346, "Mountain/Valley": 172}
    checks["table_has_both_environments"] = set(table["environment"].astype(str)) == set(ENVIRONMENTS)
    checks["source_track_weights_unit_mass"] = bool(np.allclose(source.groupby("track_id")["analysis_weight"].sum().to_numpy(float), 1.0))
    quantile_checks: dict[str, bool] = {}
    for environment in ENVIRONMENTS:
        source_group = source.loc[source["environment_class"] == environment]
        table_row = table.loc[table["environment"] == environment].iloc[0]
        values = source_group["doppler_offset_hz"].to_numpy(float)
        weights = source_group["analysis_weight"].to_numpy(float)
        expected = {f"P{q}_hz": weighted_quantile(values, weights, q / 100.0) for q in (10, 50, 90)}
        quantile_checks[environment] = all(np.isclose(float(table_row[field]), value) for field, value in expected.items())
    checks["quantiles_recomputed_from_source"] = all(quantile_checks.values())
    checks["quantiles_ordered"] = bool((table["P10_hz"] <= table["P50_hz"]).all() and (table["P50_hz"] <= table["P90_hz"]).all())
    checks["artifacts_nonempty"] = all(path.exists() and path.stat().st_size > 0 for path in [table_path, model_path, *figure_paths])
    checks["no_formal_manuscript_target"] = not any(path.name == "main.tex" for path in [table_path, model_path, *figure_paths])
    status = "PASS_WITH_LIMITATIONS" if all(checks.values()) else "FAIL"
    result = {
        "status": status,
        "checks": checks,
        "quantile_checks": quantile_checks,
        "source_sha256": sha256_file(SOURCE_PATH),
        "review_only": True,
        "limitations": [
            "The empirical CDF is descriptive and resamples the measured support; it does not establish a universal Doppler law.",
            "No formal KS p-value is reported because the observations are weighted and scene/track clustered.",
        ],
    }
    output_path = REVIEW_ROOT / "qa/signed_doppler_empirical_independent_qa.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = REVIEW_ROOT / "qa/SIGNED_DOPPLER_EMPIRICAL_QA_REPORT.md"
    report_path.write_text(
        "# Signed relative-Doppler empirical model QA\n\n"
        f"Status: **{status}**\n\n"
        "The source population was reloaded independently. Track weights, denominators, and P10/P50/P90 values were recomputed from the source CSV. No manuscript, SAGE output, raw IQ, or formal evidence file was modified.\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
