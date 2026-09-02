from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.sage_pipeline.rain.prepare_rain_sage_single_task_request import (
    build_manifest,
    expected_output_namespace,
    resolve_not_started_task,
    write_request,
)


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "sage_pipeline" / "rain" / "prepare_rain_sage_single_task_request.py"


def test_resolves_only_the_frozen_midrain_g24_channel() -> None:
    task = resolve_not_started_task(ROOT, "F1023_midrain", "G24", 8)

    assert task["scene_id"] == "F1023_midrain"
    assert task["prn"] == "G24"
    assert task["tracking_channel"] == 8
    assert task["sample_rate_hz"] == 10_230_000
    assert task["current_status"] == "NOT_STARTED"
    assert task["output_exists_at_preparation"] is False


def test_rejects_wrong_channel_or_already_started_task() -> None:
    with pytest.raises(ValueError, match="exactly one frozen NOT_STARTED task"):
        resolve_not_started_task(ROOT, "F1023_midrain", "G24", 9)
    with pytest.raises(ValueError, match="NOT_STARTED"):
        resolve_not_started_task(ROOT, "F1023_heavyrain", "G02", 1)


def test_build_manifest_is_new_only_and_does_not_read_raw_bytes(tmp_path: Path) -> None:
    manifest = build_manifest(
        ROOT,
        scene_id="F1023_midrain",
        prn="G24",
        channel=8,
        request_dir=tmp_path / "request",
        compute_raw_hash=False,
    )

    assert manifest["schema_version"] == "rain-sage-fresh-rerun-request-v1"
    assert manifest["request_class"] == "new_only_single_task_v1"
    assert manifest["task"]["scene_id"] == "F1023_midrain"
    assert manifest["task"]["prn"] == "G24"
    assert manifest["task"]["tracking_channel"] == 8
    assert manifest["execution"]["execution_mode"] == "new_only"
    assert manifest["execution"]["new_only"] is True
    assert manifest["execution"]["resume_allowed"] is False
    assert manifest["execution"]["max_parallel_matlab"] == 1
    assert manifest["output"]["namespace"] == str(
        expected_output_namespace(ROOT, "F1023_midrain", "G24")
    )
    assert manifest["provenance"]["gold_labels_used_for_selection"] is False
    assert manifest["provenance"]["previous_output_exists_at_preparation"] is False
    assert manifest["inputs"]["raw_iq"]["sha256_status"] == "NOT_COMPUTED_IN_UNIT_TEST"


def test_write_request_is_immutable_and_hash_matches_bytes(tmp_path: Path) -> None:
    manifest = {"schema_version": "rain-sage-single-task-request-v1", "value": 7}
    request_dir = tmp_path / "request"

    manifest_path, digest = write_request(manifest, request_dir)
    payload = manifest_path.read_bytes()

    assert digest == hashlib.sha256(payload).hexdigest()
    assert json.loads(payload.decode("utf-8"))["value"] == 7
    with pytest.raises(FileExistsError):
        write_request(manifest, request_dir)


def test_preparer_can_start_as_a_direct_cli_script() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Prepare one immutable" in completed.stdout
