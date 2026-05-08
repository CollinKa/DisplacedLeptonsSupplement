#!/usr/bin/env python3
"""
Summarize verify_nano.py JSON results across all datasets.

Usage:
    python check_verify_results.py
    python check_verify_results.py --results-dir verify_results/
    python check_verify_results.py --dataset ST_tW_top_UL18_customNanoAOD
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", default="verify_results", metavar="DIR",
                        help="Directory containing per-dataset result subdirectories (default: verify_results/)")
    parser.add_argument("--dataset", default=None, metavar="NAME",
                        help="Check only this dataset subdirectory")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"ERROR: {results_dir} does not exist.")
        return

    if args.dataset:
        json_files = sorted((results_dir / args.dataset).glob("*.json"))
    else:
        json_files = sorted(results_dir.rglob("*.json"))

    if not json_files:
        print("No result files found.")
        return

    n_pass = 0
    n_fail = 0
    n_warn = 0
    failures = []
    warnings = []

    for path in json_files:
        try:
            with open(path) as f:
                result = json.load(f)
        except Exception as e:
            print(f"WARNING: could not read {path}: {e}")
            continue

        status = result.get("status", "UNKNOWN")
        n_not_found = result.get("n_not_in_central", 0)
        label = f"{path.parent.name}/{path.stem}"

        if status == "PASS":
            n_pass += 1
        else:
            n_fail += 1
            failed_branches = {
                b: info for b, info in result.get("branches", {}).items()
                if not info.get("ok", True)
            }
            failures.append((label, failed_branches, n_not_found))

        if n_not_found > 0 and status == "PASS":
            n_warn += 1
            warnings.append((label, n_not_found))

    # --- Report ---
    total = n_pass + n_fail
    print(f"\n{'='*65}")
    print(f"RESULTS: {total} file(s) checked — {n_pass} PASS, {n_fail} FAIL, {n_warn} WARN")
    print(f"{'='*65}")

    if failures:
        print(f"\nFAILURES ({n_fail}):")
        for label, branches, n_not_found in failures:
            print(f"\n  {label}")
            if n_not_found:
                print(f"    WARN: {n_not_found} events not found in central file")
            for branch, info in branches.items():
                print(f"    FAIL  {branch}: {info['mismatches']} mismatch(es)")
                for ex in info.get("examples", []):
                    print(f"          {ex}")

    if warnings:
        print(f"\nWARNINGS — passed but some events not found centrally ({n_warn}):")
        for label, n_not_found in warnings:
            print(f"  {label}: {n_not_found} events not found in central file")

    if not failures and not warnings:
        print("\nAll files passed.")


if __name__ == "__main__":
    main()
