from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.audit_main_path_common_gain_fade_model import (
    _check_receipt_and_policy,
    audit_model,
)


def test_auditor_rejects_missing_model_namespace(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        audit_model(tmp_path, tmp_path / "missing")


def test_auditor_does_not_accept_empty_or_incomplete_manifest(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "model_manifest.json").write_text("{}", encoding="utf-8")
    result = audit_model(tmp_path, model)
    assert result["overall_status"] == "FAIL"
    assert result["gold_labels_used_for_selection"] is False


def test_receipt_business_status_does_not_overwrite_qa_status(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "run_receipt.json").write_text(
        '{"status":"completed","raw_iq_read":false,"matlab_executed":false,'
        '"sage_executed":false,"batch_executed":false,'
        '"gold_labels_used_for_selection":false,"output_files":["x"],"output_hashes":{"x":"h"}}',
        encoding="utf-8",
    )
    checks: dict[str, object] = {}
    _check_receipt_and_policy(model, checks)  # type: ignore[arg-type]
    assert checks["run_receipt"]["status"] == "PASS"  # type: ignore[index]
