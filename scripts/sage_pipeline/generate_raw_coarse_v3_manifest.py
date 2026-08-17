"""Create the immutable v3 parameter/schema manifest before gold replay."""

from __future__ import annotations

import argparse
from pathlib import Path

import raw_coarse_v3_common as common


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=common.PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation" / "batch_sampled_v1_3_parameter_manifest_20260812",
    )
    parser.add_argument("--project-root", type=Path, default=common.PROJECT_ROOT)
    args = parser.parse_args()
    path, digest = common.write_frozen_manifest(args.output_root, args.project_root)
    print(f"V3_PARAMETER_MANIFEST={path}")
    print(f"V3_PARAMETER_MANIFEST_SHA256={digest}")
    print(f"V3_PARAMETER_SHA256={common.parameter_sha256()}")
    print("GOLD_LABELS_USED_FOR_SELECTION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

