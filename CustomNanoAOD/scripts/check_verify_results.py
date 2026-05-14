#!/usr/bin/env python3
"""
Summarize verify_custom_nanoaod.py JSON results across all datasets.

Usage:
    python check_verify_results.py
    python check_verify_results.py --results-dir verify_results/
    python check_verify_results.py --dataset DoubleMuon_Run2022C_customNanoAOD
"""

import argparse
import json
from pathlib import Path


def _comparison_status(comparison):
    """Return (all_passed, n_failed_branches, n_not_in_central)."""
    branches = comparison.get("branches", {})
    n_failed = sum(1 for b in branches.values() if b.get("status") == "fail")
    n_not_in_central = comparison.get("n_events_not_in_central", 0)
    return n_failed == 0, n_failed, n_not_in_central


def _print_comparison_failures(label, comparison, indent="    "):
    branches = comparison.get("branches", {})
    for branch, info in branches.items():
        if info.get("status") != "fail":
            continue
        print(f"{indent}FAIL  {branch}: {info['n_mismatches']} mismatch(es)")
        for err in info.get("errors", []):
            print(f"{indent}      {err}")


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

    n_pass = n_fail = n_warn = 0
    failures = []
    warnings = []

    for path in json_files:
        try:
            with open(path) as f:
                result = json.load(f)
        except Exception as e:
            print(f"WARNING: could not read {path}: {e}")
            continue

        label = f"{path.parent.name}/{path.stem}"
        nano = result.get("nano_comparison", {})
        mini = result.get("mini_comparison")

        nano_ok, nano_n_fail, nano_missing = _comparison_status(nano)
        mini_ok, mini_n_fail, mini_missing = _comparison_status(mini) if mini else (True, 0, 0)

        all_ok = nano_ok and mini_ok
        any_missing = nano_missing + mini_missing

        if all_ok:
            if any_missing:
                n_warn += 1
                warnings.append((label, nano_missing, mini_missing))
            else:
                n_pass += 1
        else:
            n_fail += 1
            failures.append((label, nano, mini, nano_missing, mini_missing))

    total = n_pass + n_fail + n_warn
    print(f"\n{'='*65}")
    print(f"RESULTS: {total} file(s) checked — {n_pass} PASS, {n_fail} FAIL, {n_warn} WARN")
    print(f"{'='*65}")

    if failures:
        print(f"\nFAILURES ({n_fail}):")
        for label, nano, mini, nano_missing, mini_missing in failures:
            print(f"\n  {label}")
            if nano_missing:
                print(f"    {nano_missing} events not found in central NanoAOD")
            _print_comparison_failures("NanoAOD", nano)
            if mini:
                if mini_missing:
                    print(f"    {mini_missing} events not found in MiniAOD")
                _print_comparison_failures("MiniAOD displaced muons", mini)

    if warnings:
        print(f"\nWARNINGS — passed but some events not found ({n_warn}):")
        for label, nano_missing, mini_missing in warnings:
            parts = []
            if nano_missing:
                parts.append(f"{nano_missing} not in central NanoAOD")
            if mini_missing:
                parts.append(f"{mini_missing} not in MiniAOD")
            print(f"  {label}: {', '.join(parts)}")

    if not failures and not warnings:
        print("\nAll files passed.")


if __name__ == "__main__":
    main()
