#!/usr/bin/env python3
"""
Verify a custom NanoAOD file against centrally produced NanoAOD.

Queries DAS only for the runs present in the custom file, so the lumi→file
map stays small regardless of dataset size.

Usage:
    python verify_nano.py custom.root /Dataset/Name/NANOAOD
    python verify_nano.py custom.root /Dataset/Name/NANOAOD --branches Muon_pt Muon_eta
    python verify_nano.py custom.root /Dataset/Name/NANOAOD --max-events 10000
"""

import argparse
import json
import subprocess
from collections import defaultdict

import awkward as ak
import numpy as np
import uproot

FLOAT_RTOL = 1e-5
MAX_ERRORS_PER_BRANCH = 5

DEFAULT_BRANCHES = [
    "nMuon",
    "Muon_pt", "Muon_eta", "Muon_phi",
    "Muon_dxy", "Muon_dz", "Muon_dxyErr", "Muon_dzErr",
    "Muon_charge",
    "nElectron",
    "Electron_pt", "Electron_eta", "Electron_phi",
    "Electron_dxy", "Electron_dz",
]

# XRootD redirector prefix to convert LFN → openable URL
XROOTD_PREFIX = "root://cmsxrootd.fnal.gov/"


def das_query(query):
    result = subprocess.run(
        ["dasgoclient", "--query", query, "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def build_lumi_to_file_map(dataset, runs):
    """
    Query DAS for each run in `runs` and return {(run, lumi): filepath}.
    Only queries runs present in the custom file, keeping the map small.

    NOTE: DAS JSON lumi format may vary. If this fails, inspect the raw output
    of: dasgoclient --query "file,lumi dataset=DATASET run=RUN" --json
    """
    lumi_to_file = {}
    for run in sorted(runs):
        print(f"  DAS query: run {run}")
        query = f"file,lumi dataset={dataset} run={run}"
        try:
            records = das_query(query)
        except subprocess.CalledProcessError as e:
            print(f"  WARNING: DAS query ({query}) failed for run {run}: {e.stderr.strip()}")
            continue
        for record in records:
            file_info = record.get("file", [])
            lumi_info = record.get("lumi", [])
            if not file_info or not lumi_info:
                continue
            path = file_info[0]["name"]
            lumi_numbers = lumi_info[0].get("number", [])
            for lumi in lumi_numbers:
                lumi_to_file[(run, int(lumi))] = path
    return lumi_to_file


def load_events(path, branches):
    """Open a NanoAOD file and return (arrays, set of available branch names)."""
    with uproot.open(path) as f:
        tree = f["Events"]
        available = set(tree.keys())
        to_load = ["run", "luminosityBlock", "event"] + [b for b in branches if b in available]
        arrays = tree.arrays(to_load, library="ak")
    return arrays, available


def build_event_index(events):
    """Return {(run, lumi, event): row_index} for fast lookup."""
    return {
        (int(r), int(l), int(e)): i
        for i, (r, l, e) in enumerate(
            zip(ak.to_list(events.run),
                ak.to_list(events.luminosityBlock),
                ak.to_list(events.event))
        )
    }


def extract_collection(branch):
    """Return the NanoAOD collection name for a branch, or None for scalars.

    'Muon_pt' -> 'Muon', 'nMuon' -> 'Muon', 'run' -> None.
    """
    if '_' in branch:
        return branch.split('_')[0]
    if branch.startswith('n') and len(branch) > 1 and branch[1].isupper():
        return branch[1:]
    return None


def report_branch_diff(custom_available, central_available):
    extra = sorted(custom_available - central_available)
    if extra:
        print(f"\nExtra branches in custom file ({len(extra)}):")
        for b in extra:
            print(f"  + {b}")
    else:
        print("\nNo extra branches in custom file.")

    central_collections = {extract_collection(b) for b in central_available} - {None}
    custom_collections = {extract_collection(b) for b in custom_available} - {None}
    missing = sorted(central_collections - custom_collections)
    if missing:
        print(f"\nCollections entirely missing from custom file ({len(missing)}):")
        for c in missing:
            print(f"  - {c}")
    else:
        print("\nNo collections entirely missing from custom file.")


def values_match(a, b):
    """
    Compare one event's worth of values from two branches.
    Returns (True, None) on agreement or (False, description) on mismatch.
    Handles both scalars and variable-length arrays (e.g. Muon_pt).
    """
    a, b = ak.to_list(a), ak.to_list(b)
    if isinstance(a, list):
        if len(a) != len(b):
            return False, f"length {len(a)} vs {len(b)}"
        for idx, (ai, bi) in enumerate(zip(a, b)):
            if isinstance(ai, float):
                if not np.isclose(ai, bi, rtol=FLOAT_RTOL):
                    return False, f"[{idx}] {ai:.7g} vs {bi:.7g} (rdiff {abs(ai-bi)/max(abs(bi),1e-30):.2e})"
            elif ai != bi:
                return False, f"[{idx}] {ai!r} vs {bi!r}"
        return True, None
    elif isinstance(a, float):
        if not np.isclose(a, b, rtol=FLOAT_RTOL):
            return False, f"{a:.7g} vs {b:.7g} (rdiff {abs(a-b)/max(abs(b),1e-30):.2e})"
        return True, None
    else:
        if a != b:
            return False, f"{a!r} vs {b!r}"
        return True, None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("custom_file", help="Path to custom NanoAOD file")
    parser.add_argument("dataset", help="Central NanoAOD dataset name in DAS (e.g. /X/Y/NANOAOD)")
    parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES, metavar="BRANCH",
                        help="Branches to compare (default: 15 muon/electron branches)")
    parser.add_argument("--max-events", type=int, default=None, metavar="N",
                        help="Stop after comparing N events (useful for a quick check)")
    parser.add_argument("--eos", action="store_true", help="Indicates the custom file is stored in EOS")
    args = parser.parse_args()

    # --- Load custom file ---
    print(f"\nLoading custom file: {args.custom_file}")
    custom_url = XROOTD_PREFIX + args.custom_file if args.eos else args.custom_file
    custom_events, custom_available = load_events(custom_url, args.branches)
    branches = [b for b in args.branches if b in custom_available]
    missing_from_custom = [b for b in args.branches if b not in custom_available]
    if missing_from_custom:
        print(f"  WARNING: branches absent from custom file (skipped): {missing_from_custom}")
    print(f"  {len(custom_events)} events, {len(branches)} branches to check")

    # --- Query DAS for only the runs present in this file ---
    runs = set(int(r) for r in ak.to_list(custom_events.run))
    print(f"\nQuerying DAS for {len(runs)} run(s) in dataset: {args.dataset}")
    lumi_to_file = build_lumi_to_file_map(args.dataset, runs)
    print(f"  {len(lumi_to_file)} (run, lumi) pairs mapped to central files")

    # --- Group custom row indices by which central file they belong to ---
    file_to_custom_rows = defaultdict(list)
    das_missing = []
    for i, (r, l) in enumerate(zip(ak.to_list(custom_events.run), ak.to_list(custom_events.luminosityBlock))):
        central_file = lumi_to_file.get((int(r), int(l)))
        if central_file is not None:
            file_to_custom_rows[central_file].append(i)
        else:
            das_missing.append((int(r), int(l)))

    if das_missing:
        unique_missing = set(das_missing)
        print(f"  WARNING: {len(das_missing)} events from {len(unique_missing)} (run, lumi) pairs not found in DAS")

    # --- Compare event by event, one central file at a time ---
    error_counts = defaultdict(int)
    error_examples = defaultdict(list)
    n_not_in_central = 0
    n_compared = 0
    done = False
    central_branches = []

    for central_lfn, custom_rows in file_to_custom_rows.items():
        if done:
            break

        central_url = XROOTD_PREFIX + central_lfn
        print(f"\nOpening central file ({len(custom_rows)} events expected):\n  {central_url}")
        try:
            central_events, central_available = load_events(central_url, branches)
            central_branches = central_available # Assume all central files have same branches
        except Exception as e:
            print(f"  ERROR: could not open file: {e}")
            continue

        missing_from_central = [b for b in branches if b not in central_available]
        if missing_from_central:
            print(f"  WARNING: branches absent from this central file: {missing_from_central}")
        comparable = [b for b in branches if b in central_available]

        central_index = build_event_index(central_events)

        for ci in custom_rows:
            if args.max_events is not None and n_compared >= args.max_events:
                done = True
                break

            r = int(custom_events.run[ci])
            l = int(custom_events.luminosityBlock[ci])
            e = int(custom_events.event[ci])

            xi = central_index.get((r, l, e))
            if xi is None:
                n_not_in_central += 1
                continue

            n_compared += 1
            for branch in comparable:
                ok, msg = values_match(custom_events[branch][ci], central_events[branch][xi])
                if not ok:
                    error_counts[branch] += 1
                    if len(error_examples[branch]) < MAX_ERRORS_PER_BRANCH:
                        error_examples[branch].append(f"run={r} lumi={l} event={e}: {msg}")

    # --- Compare available branches between custom and central ---
    if central_branches:
        report_branch_diff(custom_available, central_branches)

    # --- Report ---
    print(f"\n{'='*65}")
    print(f"SUMMARY")
    print(f"  Events compared           : {n_compared}")
    print(f"  Events not found centrally: {n_not_in_central}")
    if args.max_events is not None and n_compared >= args.max_events:
        print(f"  (stopped at --max-events {args.max_events})")
    print()

    any_fail = False
    for branch in branches:
        if error_counts[branch]:
            any_fail = True
            print(f"  FAIL  {branch}: {error_counts[branch]} mismatch(es)")
            for ex in error_examples[branch]:
                print(f"        {ex}")
        else:
            print(f"  OK    {branch}")

    print()
    if n_not_in_central > 0:
        print("WARN: some custom events were not found in the central file — check event selection.")
    if any_fail:
        print("FAIL: branch mismatches found.")
    else:
        print("PASS: all compared branches agree.")


if __name__ == "__main__":
    main()
