#!/usr/bin/env python3

"""
Run FSL bedpostx for each prepared subject input directory.

Expected input directory:
    derivatives/fsl/sub-xxx/bedpostx_input

Required files in each input directory:
    data.nii.gz
    nodif_brain_mask.nii.gz
    bvecs
    bvals

bedpostx writes output next to the input directory:
    derivatives/fsl/sub-xxx/bedpostx_input.bedpostX
"""

import shutil
from pathlib import Path
from time import time

from bids_path import BIDS_DIR
from utils import run


BEDPOSTX_CMD = "bedpostx_gpu"
OVERWRITE = False
REQUIRED_INPUTS = [
    "data.nii.gz",
    "nodif_brain_mask.nii.gz",
    "bvecs",
    "bvals",
]


def resolve_bids_dir() -> Path:
    """Use configured BIDS_DIR, falling back to this repository root if needed."""
    bids_dir = Path(BIDS_DIR)
    if bids_dir.exists():
        return bids_dir

    repo_root = Path(__file__).resolve().parents[1]
    if (repo_root / "derivatives").exists():
        print(f"Warning: BIDS_DIR does not exist: {bids_dir}")
        print(f"Using repository root instead: {repo_root}")
        return repo_root

    raise FileNotFoundError(f"BIDS_DIR does not exist: {bids_dir}")


def get_subjects(bids_dir: Path) -> list[str]:
    """Return BIDS subject directory names sorted by label."""
    subjects = sorted(
        path.name
        for path in bids_dir.iterdir()
        if path.is_dir() and path.name.startswith("sub-")
    )

    if not subjects:
        raise FileNotFoundError(f"No sub-* directories found in {bids_dir}")

    return subjects


def missing_inputs(input_dir: Path) -> list[Path]:
    """Return missing files required by bedpostx."""
    return [input_dir / name for name in REQUIRED_INPUTS if not (input_dir / name).exists()]


def main():
    if shutil.which(BEDPOSTX_CMD) is None:
        raise FileNotFoundError(f"{BEDPOSTX_CMD} not found on PATH")

    bids_dir = resolve_bids_dir()
    deriv_dir = bids_dir / "derivatives" / "fsl"
    script_start = time()
    completed = 0
    skipped = 0

    for sub in get_subjects(bids_dir):
        start = time()
        input_dir = deriv_dir / sub / "bedpostx_input"
        output_dir = input_dir.with_suffix(input_dir.suffix + ".bedpostX")

        if not input_dir.is_dir():
            skipped += 1
            print(f"\n{sub} missing bedpostx input directory. Skipping:")
            print(f"  {input_dir}")
            continue

        missing = missing_inputs(input_dir)
        if missing:
            skipped += 1
            print(f"\n{sub} missing required bedpostx inputs. Skipping:")
            for path in missing:
                print(f"  {path}")
            continue

        if output_dir.exists():
            if not OVERWRITE:
                skipped += 1
                print(f"\n{sub} bedpostx output already exists. Skipping:")
                print(f"  {output_dir}")
                continue

            shutil.rmtree(output_dir)

        run([
            BEDPOSTX_CMD,
            str(input_dir),
        ])

        completed += 1
        print(f"\n{sub} bedpostx finished in {time() - start:.2f} seconds:")
        print(f"  {output_dir}")

    print(
        f"\nDone. Ran bedpostx for {completed} subjects, skipped {skipped}. "
        f"Time elapsed: {time() - script_start:.2f} seconds"
    )


if __name__ == '__main__':
    main()
