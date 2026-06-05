#!/usr/bin/env python3

from time import time
from utils import run
from bids_path import BIDS_DIR

CODE_DIR = BIDS_DIR / "code"
INDEX_PATH = CODE_DIR / "index.txt"
ACQP_PATH = CODE_DIR / "acqparams.txt"

DERIV_DIR = BIDS_DIR / "derivatives" / "fsl"

NUM_THREADS = 12
NUM_SUBJECTS = 29
BET_F_VAL = 0.20

script_start = time()

for i in range(1, NUM_SUBJECTS + 1):
    start = time()

    sub = f"sub-{i:03d}"
    sub_dir = BIDS_DIR / sub
    dwi_dir = sub_dir / "dwi"

    if not dwi_dir.exists():
        print(f"DWI directory for {sub} not found. Skipping this subject.")
        continue

    out_dir = DERIV_DIR / sub / "dwi"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dwi = dwi_dir / f"{sub}_dwi.nii.gz"
    raw_bvec = dwi_dir / f"{sub}_dwi.bvec"
    raw_bval = dwi_dir / f"{sub}_dwi.bval"

    b0s = out_dir / f"{sub}_desc-b0s_dwi.nii.gz"
    mean_b0 = out_dir / f"{sub}_desc-meanb0_dwi.nii.gz"
    bet_prefix = out_dir / f"{sub}_desc-brain_b0"
    bet_mask = out_dir / f"{sub}_desc-brain_b0_mask.nii.gz"

    eddy_prefix = out_dir / f"{sub}_desc-eddy_dwi"

    required_files = [
        raw_dwi,
        raw_bvec,
        raw_bval,
        INDEX_PATH,
        ACQP_PATH,
    ]

    missing = [p for p in required_files if not p.exists()]
    if missing:
        print(f"{sub} missing required files. Skipping:")
        for p in missing:
            print(f"  {p}")
        continue

    # Extract the first 5 volumes, assumed to be b=0
    run([
        "fslroi",
        str(raw_dwi),
        str(b0s),
        "0", "5",
    ])

    # Average the first 5 b0 volumes to generate a better brain mask
    run([
        "fslmaths",
        str(b0s),
        "-Tmean",
        str(mean_b0),
    ])

    # Generate brain mask
    #
    # If output prefix is ".../sub-001_desc-brain_b0",
    # BET creates:
    #   sub-001_desc-brain_b0.nii.gz
    #   sub-001_desc-brain_b0_mask.nii.gz
    run([
        "bet",
        str(mean_b0),
        str(bet_prefix),
        "-m",
        "-R",
        "-f", str(BET_F_VAL),
    ])

    # Run eddy
    #
    # Eddy creates:
    #   sub-001_desc-eddy_dwi.nii.gz
    #   sub-001_desc-eddy_dwi.eddy_rotated_bvecs
    #   sub-001_desc-eddy_dwi.eddy_parameters
    #   etc.
    run([
        "eddy",
        f"--imain={raw_dwi}",
        f"--mask={bet_mask}",
        f"--index={INDEX_PATH}",
        f"--acqp={ACQP_PATH}",
        f"--bvecs={raw_bvec}",
        f"--bvals={raw_bval}",
        f"--out={eddy_prefix}",
        f"--nthr={NUM_THREADS}",
        "--repol",
        # "--verbose",
    ])

    print(f"\n{sub} done without error. Time elapsed: {time() - start:.2f} seconds")

print(f"\nAll subjects done. Time elapsed:  {time() - script_start:.2f} seconds")