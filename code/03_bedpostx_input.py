#!/usr/bin/env python3

"""
Prepare per-subject input directories for FSL bedpostx.

For each subject, creates:
    derivatives/fsl/sub-xxx/bedpostx_input

bedpostx expects the following filenames in that directory:
    data.nii.gz
    nodif_brain_mask.nii.gz
    bvecs
    bvals

This script only copies and renames inputs. It does not run bedpostx.
"""

import shutil
from time import time
from pathlib import Path

from bids_path import BIDS_DIR


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


def copy_input(src: Path, dst: Path) -> None:
    """Copy one bedpostx input, replacing an existing regular file if present."""
    if dst.exists() or dst.is_symlink():
        if not dst.is_file() and not dst.is_symlink():
            raise IsADirectoryError(f"Cannot replace non-file path: {dst}")
        dst.unlink()

    shutil.copy2(src, dst)


def main():
    bids_dir = resolve_bids_dir()
    deriv_dir = bids_dir / "derivatives" / "fsl"
    script_start = time()
    prepared = 0
    skipped = 0

    for sub in get_subjects(bids_dir):
        start = time()

        sub_dir = bids_dir / sub
        dwi_dir = sub_dir / "dwi"
        deriv_dwi_dir = deriv_dir / sub / "dwi"
        out_dir = deriv_dir / sub / "bedpostx_input"

        input_files = {
            deriv_dwi_dir / f"{sub}_desc-eddy_dwi.nii.gz": out_dir / "data.nii.gz",
            deriv_dwi_dir / f"{sub}_desc-brain_b0_mask.nii.gz": out_dir / "nodif_brain_mask.nii.gz",
            deriv_dwi_dir / f"{sub}_desc-eddy_dwi.eddy_rotated_bvecs": out_dir / "bvecs",
            dwi_dir / f"{sub}_dwi.bval": out_dir / "bvals",
        }

        missing = [src for src in input_files if not src.exists()]
        if missing:
            skipped += 1
            print(f"\n{sub} missing required files. Skipping:")
            for src in missing:
                print(f"  {src}")
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        for src, dst in input_files.items():
            copy_input(src, dst)

        prepared += 1
        print(f"\n{sub} bedpostx input prepared in {time() - start:.2f} seconds:")
        print(f"  {out_dir}")

    print(
        f"\nDone. Prepared {prepared} subjects, skipped {skipped}. "
        f"Time elapsed: {time() - script_start:.2f} seconds"
    )

if __name__ == '__main__':
    main()
