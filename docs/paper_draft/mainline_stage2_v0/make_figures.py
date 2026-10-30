"""Render paper V0 figures from frozen light-weight result tables only.

Usage: python docs/paper_draft/mainline_stage2_v0/make_figures.py --output-dir <new-directory>
The output directory must be empty; the script never edits source results.
"""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"
SOURCE = {
    "population": RESULTS / "v0_20261024T132210Z/population_support_by_scene.csv",
    "counts": RESULTS / "v0_20261024T132210Z/window_mpc_count_summary.csv",
    "linkage": RESULTS / "wp4_gate_ef_final_20261029T181100/stage2_mpc_cir_alpha_linkage.csv",
    "cir_scene": RESULTS / "wp4_gate_ef_final_20261029T181100/gate_f_scene_summary.csv",
    "refit": RESULTS / "wp6_20261029T154500Z_final/final_mark_model.json",
    "power_delay": RESULTS / "wp2_20261025T074332Z/power_delay_loso_by_scene.csv",
    "environment": RESULTS / "wp3_20261028T140100Z/loso_paired_deltas.csv",
    "fixed_paired": RESULTS / "wp6_gateg_fixed_doppler_bins_20261030T120121Z/paired_scene_score_comparisons.csv",
    "fixed_summary": RESULTS / "wp6_gateg_fixed_doppler_bins_20261030T120121Z/fixed_bin_scene_summary.csv",
}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load():
    d = {k: (json.loads(p.read_text(encoding="utf-8")) if k == "refit" else pd.read_csv(p))
         for k, p in SOURCE.items()}
    pop = d["population"].sort_values("scene_id").reset_index(drop=True)
    counts = d["counts"].query("scope == 'GLOBAL' and label == 'ALL'").sort_values("mpc_count")
    cir = d["cir_scene"]
    path = d["linkage"].query("modeling_role == 'MPC_CANDIDATE'").copy()
    if (len(pop), pop.run_n.sum(), pop.stage0_valid_window_n.sum(), pop.selected_window_n.sum(), pop.mpc_n.sum()) != (13, 83, 285752, 7847, 8914):
        raise ValueError("frozen population identity mismatch")
    if counts.window_n.tolist() != [3574, 1412, 1081, 1780] or counts.window_n.sum() != 7847:
        raise ValueError("selected-window count mismatch")
    if len(path) != 8914 or path.duplicated(["run_id", "window_id", "path_id"]).any():
        raise ValueError("MPC identity mismatch")
    if int(cir.cir_linked_windows.sum()) != 7847 or not cir.set_index("scene_id").cir_linked_windows.equals(pop.set_index("scene_id").selected_window_n):
        raise ValueError("CIR-window linkage mismatch")
    for width, group in d["fixed_paired"].groupby("width_hz"):
        if len(group) != 13 or group.outer_held_out_scene_id.nunique() != 13 or int(group.paired_window_n.sum()) != 4273 or int(group.unpaired_window_n.sum()) != 0:
            raise ValueError(f"fixed-bin pairing mismatch at {width} Hz")
        s = d["fixed_summary"].query("width_hz == @width").iloc[0]
        if abs(group.C0_minus_M0_nats_per_mpc.mean() - s.mean_scene_paired_delta_nats_per_mpc) > 1e-12:
            raise ValueError(f"fixed-bin macro score mismatch at {width} Hz")
    return d, pop, counts, cir, path


def save(fig, out, name):
    svg = out / f"{name}.svg"
    fig.savefig(svg, bbox_inches="tight")
    # Matplotlib's path formatter emits trailing spaces on SVG coordinate lines.
    # Normalize text-only formatting so the review diff stays meaningful.
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
    fig.savefig(out / f"{name}.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def f1(out):
    fig, ax = plt.subplots(figsize=(11, 3.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 3.5)
    ax.axis("off")
    boxes = [
        (0.1, "Vehicle GPS L1 C/A\n13 scenes; 83 runs"),
        (2.35, "GNSS-SDR + NAV\ntracking support"),
        (4.6, "Stage0: 285,752\nvalid 40-ms windows"),
        (6.85, "Stage1 screen + Stage2\n7,847 selected windows"),
        (9.1, "LOSO statistics\n8,914 estimated MPC"),
    ]
    for x, label in boxes:
        ax.add_patch(FancyBboxPatch((x, 1.73), 1.8, 1.0, boxstyle="round,pad=0.07", fc="#e5f2f4", ec="#245b66", lw=1.2))
        ax.text(x + 0.9, 2.23, label, ha="center", va="center", fontsize=8.7)
    for x in [1.92, 4.17, 6.42, 8.67]:
        ax.add_patch(FancyArrowPatch((x, 2.23), (x + 0.35, 2.23), arrowstyle="-|>", mutation_scale=12, color="#30414b"))
    ax.text(5.5, 1.05, "S = 1 denotes Stage2 selection; N = L − 1 is an estimator output, not a physical occurrence label", ha="center", fontsize=9, color="#8c2d31")
    ax.text(5.5, 0.49, "CIR/PDP read-back and complex-alpha audit: linked supporting measurements, not independent propagation truth", ha="center", fontsize=8.4, color="#355778")
    save(fig, out, "F1")


def f2(counts, out):
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    n = counts.window_n.to_numpy()
    bars = ax.bar([0, 1, 2, 3], n, color=["#477a8d", "#5c9eaa", "#83b7ba", "#b3d4d2"])
    for bar, count in zip(bars, n):
        ax.text(bar.get_x() + bar.get_width()/2, count + 80, f"{count:,}\n({count/7847:.1%})", ha="center", fontsize=9)
    ax.set(xticks=[0, 1, 2, 3], xlabel="Estimated MPC count N in a Stage2-selected window", ylabel="Selected windows (count)", ylim=(0, 4200))
    ax.set_title("Count distribution conditional on Stage2 selection (7,847 windows)")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, out, "F2")


def scene_window_weights(path):
    key = ["scene_id", "run_id", "window_id"]
    sizes = path.groupby(key).size().rename("n")
    n_windows = path[key].drop_duplicates().groupby("scene_id").size()
    n_scenes = path.scene_id.nunique()
    merged = path[key].merge(sizes.reset_index(), on=key).merge(n_windows.rename("windows_in_scene").reset_index(), on="scene_id")
    return (1.0 / n_scenes / merged.windows_in_scene / merged.n).to_numpy()


def f3(path, model, out):
    w = scene_window_weights(path)
    if abs(w.sum() - 1) > 1e-10:
        raise ValueError("plot weights do not sum to one")
    p = model["full_population_refits"]
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.1))
    d = path.excess_delay_chips.to_numpy(dtype=float)
    valid = np.isclose(d / 0.01, np.round(d / 0.01), atol=1e-7)
    if not valid.all():
        raise ValueError("delay is not on the documented 0.01-chip lattice")
    centers = np.arange(0.1, 1.001, 0.01)
    observed = np.array([w[np.isclose(d, x, atol=1e-8)].sum() for x in centers])
    q = p["excess_delay_chips"]["parameters"]
    fitted = stats.lognorm.cdf(centers + 0.005, q["shape"], loc=0, scale=q["scale"]) - stats.lognorm.cdf(centers - 0.005, q["shape"], loc=0, scale=q["scale"])
    axes[0].bar(centers, observed, width=0.008, alpha=.63, label="weighted empirical mass")
    axes[0].plot(centers, fitted, color="#a12e37", lw=1.6, label="full-data Lognormal cell mass")
    axes[0].set(xlabel="Excess delay (chips)", ylabel="Probability mass per 0.01-chip cell", title="(a) Delay, shown to 1 chip")
    v = path.doppler_offset_hz.to_numpy(dtype=float)
    bins = np.floor(v/5 + .5).astype(int)
    ks = np.arange(-40, 41)
    observed = np.array([w[bins == k].sum() for k in ks])
    q = p["doppler_offset_hz"]["parameters"]
    fitted = stats.t.cdf((ks+.5)*5, q["df"], loc=q["loc"], scale=q["scale"]) - stats.t.cdf((ks-.5)*5, q["df"], loc=q["loc"], scale=q["scale"])
    axes[1].bar(ks*5, observed, width=4.3, alpha=.68)
    axes[1].plot(ks*5, fitted, color="#a12e37", lw=1.6)
    axes[1].set(xlabel="Signed relative Doppler (Hz)", ylabel="Probability mass per fixed 5-Hz bin", title="(b) Doppler, shown ±200 Hz")
    power = path.relative_power_db.to_numpy(dtype=float)
    edges = np.arange(-25, 31, 1)
    axes[2].hist(power, bins=edges, weights=w, density=False, alpha=.68)
    q = p["relative_power_db"]["parameters"]
    xs = np.linspace(-25, 30, 500)
    fitted = stats.norm.cdf(xs + .5, loc=q["loc"], scale=q["scale"]) - stats.norm.cdf(xs - .5, loc=q["loc"], scale=q["scale"])
    axes[2].plot(xs, fitted, color="#a12e37", lw=1.6)
    axes[2].set(xlabel="Relative power (dB)", ylabel="Probability mass per 1-dB bin", title="(c) Power")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Stage2 MPC marks: scene/window-balanced descriptive display, 8,914 paths", fontsize=12)
    fig.text(.5, -.01, "Red curves: full-population descriptive refits; not held-out scores. Delay <0.10 chip is unobserved. Display truncation does not renormalize masses.", ha="center", fontsize=8.2)
    fig.tight_layout()
    save(fig, out, "F3")


def f4(pop, power, environment, out):
    labels = {scene: f"S{i:02d}" for i, scene in enumerate(pop.scene_id, 1)}
    p = power.query("scope == 'GLOBAL' and fit_status == 'PASS'").set_index("held_out_scene_id").reindex(pop.scene_id)
    if p.delta_mean_log_score.isna().any() or len(p) != 13:
        raise ValueError("power-delay LOSO support mismatch")
    e = environment.query("data_scope == 'ALL_MPC' and variable == 'excess_delay_chips' and family == 'lognormal' and comparison == 'M1-M0' and paired_status == 'PASS'")
    if len(e) != 9 or not e.same_test_identity.astype(bool).all():
        raise ValueError("environment comparison support mismatch")
    e = e.set_index("held_out_scene_id").reindex([s for s in pop.scene_id if s in e.held_out_scene_id.values])
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7.3))
    for ax, values, ids, title in [
        (axes[0], p.delta_mean_log_score.to_numpy(), pop.scene_id, "(a) Power | delay model minus marginal Normal; 13 scenes"),
        (axes[1], e.delta_window_balanced_log_score_right_minus_left.to_numpy(), e.index, "(b) Environment M1 minus global M0; delay Lognormal; 9 core scenes"),
    ]:
        x = np.arange(len(ids))
        ax.axhline(0, color="#343a40", lw=.9)
        ax.bar(x, values, color=np.where(values >= 0, "#3b8790", "#b5535a"))
        ax.set(xticks=x, xticklabels=[labels[s] for s in ids], ylabel="Paired held-out log-score difference\n(nats per MPC mark)", title=title)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.18)
    fig.text(.5, .005, "Positive favors the more complex model. Panels use different eligible scene populations; compare only within each panel.", ha="center", fontsize=8.4)
    fig.tight_layout(rect=(0, .03, 1, 1))
    save(fig, out, "F4")


def f7(pop, paired, out):
    labels = {scene: f"S{i:02d}" for i, scene in enumerate(pop.scene_id, 1)}
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 8.3), sharex=True, sharey=True)
    for ax, width in zip(axes, [5, 10, 20]):
        g = paired.query("width_hz == @width").set_index("outer_held_out_scene_id").reindex(pop.scene_id)
        y = g.C0_minus_M0_nats_per_mpc.to_numpy()
        ax.axhline(0, color="#303942", lw=.9)
        ax.scatter(np.arange(13), y, c=np.where(y >= 0, "#307e88", "#af4b55"), s=42, zorder=3)
        ax.vlines(np.arange(13), 0, y, color="#9aa9ad", lw=.7)
        ax.axhline(y.mean(), color="#7a4e96", ls="--", lw=1.1)
        ax.text(.99, .10, f"{width} Hz: macro {y.mean():+.5f}; {(y>0).sum()}+/ {(y<0).sum()}−", transform=ax.transAxes, ha="right", fontsize=9)
        ax.set(ylabel="C0 − M0\n(nats/mark)", ylim=(-.39, .15))
        ax.grid(axis="y", alpha=.17)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1].set(xticks=np.arange(13), xticklabels=[labels[s] for s in pop.scene_id], xlabel="Completely held-out scene (S01–S13; see Table 1)")
    fig.suptitle("Fixed-bin mixed score: Gaussian Copula C0 versus independent marginals M0", fontsize=12)
    fig.text(.5, .007, "Same 4,273 paired MPC-bearing selected windows per resolution; 5/10/20 Hz absolute scores are not compared across resolutions.", ha="center", fontsize=8.2)
    fig.tight_layout(rect=(0, .035, 1, .96))
    save(fig, out, "F7")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    d, pop, counts, cir, path = load()
    f1(out)
    f2(counts, out)
    f3(path, d["refit"], out)
    f4(pop, d["power_delay"], d["environment"], out)
    f7(pop, d["fixed_paired"], out)
    t1 = pop[["scene_id", "environment_class", "run_n", "stage0_valid_window_n", "selected_window_n", "mpc_n", "gsv_window_n"]].copy()
    t1.insert(0, "paper_scene", [f"S{i:02d}" for i in range(1, 14)])
    t1["cir_linked_window_n"] = t1.scene_id.map(cir.set_index("scene_id").cir_linked_windows)
    t1.to_csv(out / "T1_scene_population.csv", index=False)
    summary = d["fixed_summary"].sort_values("width_hz")
    audit = {
        "scene_n": 13, "run_n": int(pop.run_n.sum()),
        "stage0_valid_window_n": int(pop.stage0_valid_window_n.sum()),
        "selected_window_n": int(pop.selected_window_n.sum()), "mpc_n": len(path),
        "cir_linked_window_n": int(cir.cir_linked_windows.sum()),
        "count_0_1_2_3": counts.window_n.astype(int).tolist(),
        "fixed_bins": [{"width_hz": int(s.width_hz), "scene_n": int(s.scored_scene_n),
                        "positive_scene_n": int(s.scenes_positive), "negative_scene_n": int(s.scenes_negative),
                        "paired_window_n": int(s.paired_window_n),
                        "macro_delta_nats_per_mark": float(s.mean_scene_paired_delta_nats_per_mpc)}
                       for _, s in summary.iterrows()],
        "input_sha256": {key: sha(value) for key, value in SOURCE.items()},
        "plot_scope": "DESCRIPTIVE_ONLY_EXCEPT_PAIRED_HELDOUT_F4_F7",
    }
    (out / "figure_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: audit[key] for key in ("scene_n", "run_n", "selected_window_n", "mpc_n", "fixed_bins")}, indent=2))


if __name__ == "__main__":
    main()
