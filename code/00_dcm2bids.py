#!/usr/bin/env python3

"""
Convert all DICOM data to the BIDS format according to the dcm2bids config file. 

Adds a sub-xxx folder to BIDS_DIR for each subject, starting from existing + 1. 

Maintains BIDS_DIR/private/participants.tsv,
which keeps track of subject-id, original subject dir name, and subject group.

Assumes:
1. Raw data are located in BIDS_DIR/sourcedata, 
grouped by treatment (e.g., sourcedata/group1,
sourcedata/group2)

2. Every subject only has one session.

Does not check config, so beware of duplicates/missing files.

Usage:
python3 00_dcm2bids <path_to_config>
"""

from time import time
from utils import run
from bids_path import BIDS_DIR
from pathlib import Path
import re
import sys
import csv


def get_existing_max_id(out_dir):
    """
    Look for existing BIDS subject directories like:
        sub-001
        sub-002
        sub-123

    Return the maximum numeric ID found.
    """
    max_id = 0
    pattern = re.compile(r"^sub-(\d+)$")

    if not out_dir.exists():
        return 0

    for path in out_dir.iterdir():
        if not path.is_dir():
            continue

        match = pattern.match(path.name)
        if match:
            max_id = max(max_id, int(match.group(1)))

    return max_id


def ensure_private_participants_header(participants_path):
    participants_path.parent.mkdir(parents=True, exist_ok=True)

    if participants_path.exists() and participants_path.stat().st_size > 0:
        return

    with participants_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["participant_id", "original_subject_dir", "group"])


def append_private_participant(participants_path, participant_id, original_subject_dir, group):
    ensure_private_participants_header(participants_path)

    with participants_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow([participant_id, original_subject_dir, group])


def main():
    start = time()

    if len(sys.argv) != 2:
        sys.exit("Usage: python3 00_dcm2bids <path_to_config>")

    config_path = Path(sys.argv[1])

    if not config_path.is_file():
        sys.exit(f"Config file does not exist: {config_path}")

    bids_dir = Path(BIDS_DIR)
    sourcedata_dir = bids_dir / "sourcedata"
    private_participants = bids_dir / "private" / "participants.tsv"

    if not bids_dir.is_dir():
        sys.exit(f"BIDS_DIR does not exist or is not a directory: {bids_dir}")

    if not sourcedata_dir.is_dir():
        sys.exit(f"sourcedata directory does not exist: {sourcedata_dir}")

    ensure_private_participants_header(private_participants)

    next_id = get_existing_max_id(bids_dir) + 1

    print(f"BIDS_DIR: {bids_dir}")
    print(f"sourcedata: {sourcedata_dir}")
    print(f"config: {config_path}")
    print(f"Existing max subject ID: {next_id - 1:03d}")
    print(f"Starting from subject ID: {next_id:03d}")

    group_dirs = sorted(
        path for path in sourcedata_dir.iterdir()
        if path.is_dir()
    )

    if not group_dirs:
        print(f"No group directories found in {sourcedata_dir}")
        return

    for group_dir in group_dirs:
        group = group_dir.name

        subject_dirs = sorted(
            path for path in group_dir.iterdir()
            if path.is_dir()
        )

        if not subject_dirs:
            print(f"No subject directories found in group: {group}")
            continue

        for subject_dir in subject_dirs:
            participant_label = f"{next_id:03d}"
            participant_id = f"sub-{participant_label}"

            print()
            print(f"Converting: {subject_dir}")
            print(f"Group: {group}")
            print(f"Assigned ID: {participant_id}")

            run([
                "dcm2bids",
                "-d", str(subject_dir),
                "-p", participant_label,
                "-c", str(config_path),
                "-o", str(bids_dir),
            ])

            append_private_participant(
                participants_path=private_participants,
                participant_id=participant_id,
                original_subject_dir=subject_dir.name,
                group=group,
            )

            print(f"Recorded {participant_id} -> {subject_dir.name}, group={group}")

            next_id += 1

    elapsed = time() - start
    print()
    print(f"Done. Elapsed time: {elapsed:.1f} seconds")


if __name__ == "__main__":
    main()