"""Run independent output audits and write the VTC validation QA report."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
OUT = ROOT / "docs/vtc2027_spring/evidence/validation_v1"
CONTRACT = OUT / "validation_contract.json"
REPORT = ROOT / "docs/vtc2027_spring/evidence/VTC_THREE_LAYER_DLL_VALIDATION_QA_REPORT.md"
MANIFEST = OUT / "validation_manifest.json"


def load_module(name: str):
    path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_audit(module_name: str) -> tuple[str, dict | None, str | None]:
    try:
        required_output = {
            "audit_layer1_outputs": OUT / "layer1_controlled_trials.csv",
            "audit_layer2_outputs": OUT / "layer2_multipath_stress_trials.csv",
            "audit_layer3_outputs": OUT / "layer3_native_model_support.csv",
            "audit_dll_code_bias_outputs": OUT / "dll_code_bias_cases.csv",
        }[module_name]
        if not required_output.is_file():
            return "BLOCKED", None, f"missing experiment output: {required_output}"
        module = load_module(module_name)
        result = module.audit_outputs()
        return "PASS", result, None
    except FileNotFoundError as exc:
        return "BLOCKED", None, str(exc)
    except AssertionError as exc:
        return "FAIL", None, str(exc)
    except Exception as exc:  # pragma: no cover - report must preserve unexpected failures
        return "FAIL", None, "".join(traceback.format_exception_only(type(exc), exc)).strip()


def gate_from_outputs(contract: dict) -> dict:
    gate = {
        "layer1_minus5_rate": None,
        "layer1_minus10_rate": None,
        "layer2_minus8_rate": None,
        "layer2_minus12_rate": None,
        "dll_improved_event_count": None,
        "recommendation": "BLOCKED",
    }
    layer1_path = OUT / "layer1_controlled_trials.csv"
    layer2_path = OUT / "layer2_multipath_stress_trials.csv"
    dll_path = OUT / "dll_code_bias_cases.csv"
    if not (layer1_path.is_file() and layer2_path.is_file() and dll_path.is_file()):
        return gate
    layer1 = read_csv(layer1_path)
    layer2 = read_csv(layer2_path)
    dll = read_csv(dll_path)

    def rate(rows: list[dict[str, str]], key: str, value: float) -> float:
        subset = [row for row in rows if float(row[key]) == value]
        return sum(row["injected_match"].strip().lower() in {"1", "true"} for row in subset) / max(len(subset), 1)

    gate["layer1_minus5_rate"] = rate(layer1, "relative_power_truth_db", -5.0)
    gate["layer1_minus10_rate"] = rate(layer1, "relative_power_truth_db", -10.0)
    gate["layer2_minus8_rate"] = rate(layer2, "relative_power_truth_db", -8.0)
    gate["layer2_minus12_rate"] = rate(layer2, "relative_power_truth_db", -12.0)

    pre = {}
    aware = {}
    for row in dll:
        if row["valid_crossing"].strip().lower() not in {"1", "true"}:
            continue
        event = row["event_label"]
        if row["mode"] == "pre_cancellation":
            pre.setdefault(event, []).append(float(row["absolute_bias_m"]))
        elif row["mode"] == "error_aware_cancellation":
            aware.setdefault(event, []).append(float(row["absolute_bias_m"]))
    improved = 0
    for event in sorted(set(pre) & set(aware)):
        pre_median = sorted(pre[event])[len(pre[event]) // 2]
        aware_median = sorted(aware[event])[len(aware[event]) // 2]
        improved += aware_median < pre_median
    gate["dll_improved_event_count"] = improved
    gate["recommendation"] = "PASS" if (
        gate["layer1_minus5_rate"] >= 0.80
        and gate["layer1_minus10_rate"] >= 0.80
        and gate["layer2_minus8_rate"] >= 0.70
        and gate["layer2_minus12_rate"] >= 0.70
        and improved >= 3
    ) else "FAIL"
    return gate


def write_report(statuses: dict[str, str], details: dict[str, dict | None], gate: dict) -> None:
    lines = [
        "# VTC Three-Layer and DLL Validation QA Report",
        "",
        f"- QA time (UTC): `{datetime.now(timezone.utc).isoformat()}`",
        "- Scope: Layer 1 controlled recovery, Layer 2 multipath stress, Layer 3 native model support, DLL code-bias case study",
        "- Production namespace modified: `NO`",
        "- Manuscript modified: `NO`",
        "",
        "## Independent verdicts",
        "",
    ]
    for name, status in statuses.items():
        lines.append(f"- `{name}`: **{status}**")
        if details.get(name):
            lines.append(f"  - {json.dumps(details[name], ensure_ascii=False, sort_keys=True)}")
    lines.extend([
        "",
        "## Predeclared paper-admission gate",
        "",
        f"- Layer 1 recovery at -5 dB: `{gate['layer1_minus5_rate']}` (required >= 0.80)",
        f"- Layer 1 recovery at -10 dB: `{gate['layer1_minus10_rate']}` (required >= 0.80)",
        f"- Layer 2 recovery at -8 dB: `{gate['layer2_minus8_rate']}` (required >= 0.70)",
        f"- Layer 2 recovery at -12 dB: `{gate['layer2_minus12_rate']}` (required >= 0.70)",
        f"- DLL events with lower error-aware median absolute bias: `{gate['dll_improved_event_count']}` (required >= 3/4)",
        f"- Paper-admission recommendation: **{gate['recommendation']}**",
        "",
        "## Scientific interpretation boundary",
        "",
        "- Layer 1 backgrounds are not labeled LOS or multipath-free.",
        "- Only injected paths have known truth in Layers 1--2; native paths are consistency references.",
        "- Layer 3 is native model-fit support, not physical-reflector ground truth.",
        "- DLL output is a signal-level receiver-model result, not PVT, pseudorange, or positioning improvement.",
        "",
        "## Gate",
        "",
        "The report stops here. Manuscript integration requires a separate author/Commander admission decision.",
        "",
    ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    audit_specs = {
        "LAYER1_CONTROLLED_QA": "audit_layer1_outputs",
        "LAYER2_MULTIPATH_STRESS_QA": "audit_layer2_outputs",
        "LAYER3_NATIVE_MODEL_QA": "audit_layer3_outputs",
        "DLL_BIAS_QA": "audit_dll_code_bias_outputs",
    }
    statuses: dict[str, str] = {}
    details: dict[str, dict | None] = {}
    for label, module_name in audit_specs.items():
        status, result, error = run_audit(module_name)
        statuses[label] = status
        details[label] = result if result is not None else {"error": error}
    gate = gate_from_outputs(contract)
    statuses["PAPER_ADMISSION_RECOMMENDATION"] = gate["recommendation"]
    details["PAPER_ADMISSION_RECOMMENDATION"] = gate
    write_report(statuses, details, gate)
    manifest = {
        "qa_report": str(REPORT),
        "contract_sha256": sha256(CONTRACT),
        "statuses": statuses,
        "gate": gate,
        "paper_admission_authorized": False,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if all(status in {"PASS", "FAIL", "BLOCKED"} for status in statuses.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
