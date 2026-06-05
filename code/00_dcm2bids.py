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

Only adds a subject to BIDS if every config description has exactly one match
among dcm2bids_helper-generated sidecar JSON files.

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
import json
import fnmatch
import shutil
import subprocess


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


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


def value_matches(actual, expected):
    """
    Approximate dcm2bids criteria matching.

    Supports:
    - exact equality for numbers/bools
    - shell-style wildcards for strings, e.g. "*DTI*"
    - list of accepted values
    """
    if isinstance(expected, list):
        return any(value_matches(actual, item) for item in expected)

    if isinstance(expected, str):
        return fnmatch.fnmatchcase(str(actual), expected)

    return actual == expected


def sidecar_matches_criteria(sidecar, criteria):
    for key, expected in criteria.items():
        if key not in sidecar:
            return False

        if not value_matches(sidecar[key], expected):
            return False

    return True


def description_label(desc, idx):
    label_parts = []

    for key in ("id", "datatype", "suffix", "customLabels", "custom_entities"):
        if key in desc:
            label_parts.append(f"{key}={desc[key]}")

    if label_parts:
        return ", ".join(label_parts)

    return f"description[{idx}]"


def check_config_exactly_one_match(config_path, helper_dir):
    """
    Return (ok, messages).

    ok=True means every config descriptions[] entry has exactly one matching
    helper JSON sidecar.
    """
    config = load_json(config_path)
    descriptions = config.get("descriptions", [])

    if not descriptions:
        return False, ["Config has no descriptions[] entries."]

    helper_dir = Path(helper_dir)

    sidecars = []
    for path in sorted(helper_dir.glob("*.json")):
        try:
            sidecars.append((path.name, load_json(path)))
        except Exception as e:
            return False, [f"Could not read helper JSON {path}: {e}"]

    if not sidecars:
        return False, [f"No helper JSON sidecars found in {helper_dir}"]

    messages = []
    failed = []

    for idx, desc in enumerate(descriptions):
        criteria = desc.get("criteria")
        label = description_label(desc, idx)

        if not criteria:
            failed.append((label, "missing or empty criteria", []))
            continue

        matched = [
            filename
            for filename, sidecar in sidecars
            if sidecar_matches_criteria(sidecar, criteria)
        ]

        if len(matched) != 1:
            failed.append((label, criteria, matched))

    if failed:
        messages.append("Config check failed: not every description matched exactly one helper sidecar.")

        for label, criteria, matched in failed:
            messages.append(f"  Failed: {label}")
            messages.append(f"    criteria: {criteria}")
            messages.append(f"    matched {len(matched)} files")

            for name in matched:
                messages.append(f"      - {name}")

        return False, messages

    return True, ["Config check passed: every description matched exactly one helper sidecar."]


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
    tmp_dir = bids_dir / "tmp_dcm2bids"

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
            print(f"Checking: {subject_dir}")
            print(f"Group: {group}")
            print(f"Candidate ID: {participant_id}")

            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)

            try:
                run([
                    "dcm2bids_helper",
                    "-d", str(subject_dir),
                    "-o", str(bids_dir),
                ])
            except subprocess.CalledProcessError:
                print(f"Skipping {subject_dir}: dcm2bids_helper failed.", file=sys.stderr)
                continue

            helper_dir = tmp_dir / "helper"

            ok, messages = check_config_exactly_one_match(
                config_path=config_path,
                helper_dir=helper_dir,
            )

            for message in messages:
                print(message, file=sys.stdout if ok else sys.stderr)

            if not ok:
                print(f"Skipping {subject_dir}: config did not match exactly once for every entry.")
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir)
                continue

            print(f"Converting: {subject_dir}")
            print(f"Assigned ID: {participant_id}")

            try:
                run([
                    "dcm2bids",
                    "-d", str(subject_dir),
                    "-p", participant_label,
                    "-c", str(config_path),
                    "-o", str(bids_dir),
                ])
            except subprocess.CalledProcessError:
                print(f"dcm2bids failed for {subject_dir}; ID was not recorded.", file=sys.stderr)
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir)
                continue

            append_private_participant(
                participants_path=private_participants,
                participant_id=participant_id,
                original_subject_dir=subject_dir.name,
                group=group,
            )

            print(f"Recorded {participant_id} -> {subject_dir.name}, group={group}")

            next_id += 1

            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)

    elapsed = time() - start
    print()
    print(f"Done. Elapsed time: {elapsed:.1f} seconds")


if __name__ == "__main__":
    main()