#!/usr/bin/env python3

from time import time
from utils import run
from bids_path import BIDS_DIR

"""
Performs individual and group level eddy QC.

Individual outputs are stored at derivatives/fsl/sub-xxx/eddy_qc
The group result is stored at derivatives/fsl/eddy_qc
"""

NUM_SUBJECTS = 29


def main():
    CODE_DIR = BIDS_DIR / "code"
    INDEX_PATH = CODE_DIR / "index.txt"
    ACQP_PATH = CODE_DIR / "acqparams.txt"

    DERIV_DIR = BIDS_DIR / "derivatives" / "fsl"
    MAIN_QC_DIR = DERIV_DIR / "eddy_qc"

    TEMP_QC_LIST = DERIV_DIR / "temp_qc_list.txt"
    start = time()
    for i in range(1, NUM_SUBJECTS + 1):

        sub = f"sub-{i:03d}"
        dwi_dir = BIDS_DIR / sub / "dwi"
        deriv_dwi_dir = DERIV_DIR / sub / "dwi"

        bvals = dwi_dir / f"{sub}_dwi.bval"
        eddy_prefix = deriv_dwi_dir / f"{sub}_desc-eddy_dwi"
        mask = deriv_dwi_dir / f"{sub}_desc-brain_b0_mask.nii.gz"

        out = DERIV_DIR / sub / "eddy_qc"

        if out.exists():
            yn = input(f"Warning: Output directory {out} already exists."
                    "\nPress y to overwrite its contents and n to skip {sub}.").lower()
            if yn == "y":
                run([
                    "rm",
                    "-rf",
                    str(out)
                ])
            else:
                continue

        run([
            "eddy_quad",
            str(eddy_prefix),
            "-idx", str(INDEX_PATH),
            "-par", str(ACQP_PATH),
            "-m", str(mask),
            "-b", str(bvals),
            "-o", str(out)
        ])
        
        with open(TEMP_QC_LIST, "a") as file:
            file.write(str(out)+"\n") 

    if MAIN_QC_DIR.exists():
        yn = input(f"Warning: Output directory {MAIN_QC_DIR} already exists. \nOverwrite its contents? (y/n).").lower()
        if yn == "y":
            run([
                "rm",
                "-rf",
                str(MAIN_QC_DIR)
            ])
            run([
                "eddy_squad",
                str(TEMP_QC_LIST),
                "-o", str(MAIN_QC_DIR/"group_report")
            ])

    run([
        "rm",
        str(TEMP_QC_LIST)
    ])

    print(f"\nAll subjects done. Time elapsed: {time() - start:.2f} seconds")


if __name__ == '__main__':
    main()