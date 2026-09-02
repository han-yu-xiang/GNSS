"""Fail-closed Python-only sequence runner for the approved VTC validation."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/vtc2027_spring/evidence/validation_v1"
CONTRACT = OUT / "validation_contract.json"
STATE = OUT / "python_validation_runner_state.json"
LOCK = OUT / ".python_validation_active.lock"


@dataclass(frozen=True)
class Step:
    name: str
    arguments: tuple[str, ...]


def build_steps() -> list[Step]:
    base = "scripts/analysis/vtc_validation/"
    return [
        Step("layer1", (base + "run_layer1_controlled_recovery.py",)),
        Step("layer1_audit", (base + "test_layer1_outputs.py",)),
        Step("layer2", (base + "run_layer2_multipath_stress.py",)),
        Step("layer2_audit", (base + "test_layer2_outputs.py",)),
        Step("layer3_audit", (base + "test_layer3_outputs.py",)),
        Step("dll", (base + "run_dll_code_bias_study.py",)),
        Step("dll_audit", (base + "test_dll_code_bias_outputs.py",)),
        Step("independent_qa", (base + "run_independent_qa.py",)),
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_state(status: str, step: str = "", completed: list[str] | None = None, error: str = "") -> None:
    payload = {
        "status": status,
        "current_step": step,
        "completed_steps": completed or [],
        "error": error,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "matlab_interaction": False,
        "production_runner_interaction": False,
        "max_parallel_python": 1,
    }
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    implementation = contract["implementation"]
    if contract["production_execution"] or contract["resume"]:
        raise RuntimeError("contract is not isolated from production/resume")
    if implementation["language"] != "python" or implementation["max_workers"] != 1:
        raise RuntimeError("contract does not authorize single-worker Python execution")
    if any(
        implementation[key]
        for key in ("matlab_process_started", "matlab_process_attached", "production_runner_interaction")
    ):
        raise RuntimeError("contract permits prohibited MATLAB/production interaction")
    for source in implementation["entrypoints"] + implementation["modules"]:
        path = ROOT / source["path"]
        if sha256(path) != source["sha256"]:
            raise RuntimeError(f"implementation hash mismatch: {path}")
    forbidden_existing = [
        OUT / "layer1_controlled_trials.csv",
        OUT / "layer2_multipath_stress_trials.csv",
        OUT / "dll_code_bias_cases.csv",
    ]
    existing = [str(path) for path in forbidden_existing if path.exists()]
    if existing:
        raise RuntimeError(f"new-only validation outputs already exist: {existing}")
    return contract


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        raise RuntimeError(f"validation lock already exists: {LOCK}")
    preflight()
    LOCK.open("x", encoding="utf-8").write(
        json.dumps({"pid": os.getpid(), "started_at_utc": datetime.now(timezone.utc).isoformat()})
    )
    completed: list[str] = []
    env = os.environ.copy()
    env.update({
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    })
    creationflags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    try:
        write_state("RUNNING", completed=completed)
        for step in build_steps():
            write_state("RUNNING", step.name, completed)
            stdout_path = OUT / f"python_sequence_{step.name}.stdout.log"
            stderr_path = OUT / f"python_sequence_{step.name}.stderr.log"
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr:
                process = subprocess.Popen(
                    [sys.executable, *step.arguments],
                    cwd=ROOT,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    creationflags=creationflags,
                )
                return_code = process.wait()
            if return_code != 0:
                error = f"step {step.name} exited with code {return_code}"
                write_state("FAILED", step.name, completed, error)
                return return_code
            completed.append(step.name)
        write_state("COMPLETED", completed=completed)
        return 0
    except Exception as exc:
        write_state("FAILED", completed=completed, error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
