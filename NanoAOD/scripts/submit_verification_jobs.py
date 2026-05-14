#!/usr/bin/env python3
"""
Get CRAB output file list, map each to its central NanoAOD files via DAS,
and submit one Condor job per custom file to verify it.

Usage:
    python submit_verification_jobs.py crab_projects/ST_tW_top_UL18_customNanoAOD \\
        --dataset /ST_tW_top_5f_.../NANOAODSIM

    # Write submit file without submitting:
    python submit_verify.py ... --dry-run
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import awkward as ak
import uproot

XROOTD_EOS    = "root://cmseos.fnal.gov/"
XROOTD_GLOBAL = "root://cmsxrootd.fnal.gov/"

HERE = Path(__file__).parent.resolve()


# --- CRAB -------------------------------------------------------------------

def get_crab_output_lfns(task_dir):
    """Run crab getoutput --dump and return a list of output LFNs."""
    result = subprocess.run(
        ["crab", "getoutput", "-d", task_dir, "--dump"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: crab getoutput failed:\n{result.stderr.strip()}")
        sys.exit(1)

    lfns = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("LFN:"):
            lfns.append(line[len("LFN:"):].strip())
    return lfns


# --- DAS --------------------------------------------------------------------

def das_query(query):
    result = subprocess.run(
        ["dasgoclient", "--query", query, "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def build_lumi_to_file_map(dataset, runs):
    """Query DAS per run and return {(run, lumi): central_lfn}."""
    lumi_to_file = {}
    for run in sorted(runs):
        print(f"  DAS query: run {run}")
        query = f"file,lumi dataset={dataset} run={run}"
        try:
            records = das_query(query)
        except subprocess.CalledProcessError as e:
            print(f"  WARNING: DAS query failed for run {run}: {e.stderr.strip()}")
            continue
        for record in records:
            file_info = record.get("file", [])
            lumi_info = record.get("lumi", [])
            if not file_info or not lumi_info:
                continue
            path = file_info[0]["name"]
            for lumi in lumi_info[0].get("number", []):
                lumi_to_file[(run, int(lumi))] = path
    return lumi_to_file


# --- Custom file ------------------------------------------------------------

def get_run_lumi_pairs(lfn):
    """Open a custom EOS file and return the set of (run, lumi) pairs."""
    url = XROOTD_EOS + lfn
    with uproot.open(url) as f:
        arrays = f["Events"].arrays(["run", "luminosityBlock"], library="ak")
    return set(zip(ak.to_list(arrays.run), ak.to_list(arrays.luminosityBlock)))


# --- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("task_dir",
                        help="CRAB task directory (e.g. crab_projects/ST_tW_top_UL18_customNanoAOD)")
    parser.add_argument("--dataset", required=True,
                        help="Central NanoAOD dataset in DAS (e.g. /ST_tW_top_.../NANOAODSIM)")
    parser.add_argument("--results-dir", default="verify_results", metavar="DIR",
                        help="Directory for per-file JSON results (default: verify_results/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write submit file but do not call condor_submit")
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve() / Path(args.task_dir).name
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = Path("logs").resolve()
    logs_dir.mkdir(exist_ok=True)

    # --- Get custom file LFNs from CRAB -------------------------------------
    print("Getting output file list from CRAB...")
    lfns = get_crab_output_lfns(args.task_dir)
    if not lfns:
        print("ERROR: no LFNs found in crab getoutput output.")
        sys.exit(1)
    print(f"  {len(lfns)} custom file(s) found")

    # --- Read run/lumi from each custom file --------------------------------
    print("\nReading run/lumi from custom files (opens each file via XRootD)...")
    file_pairs = {}
    all_runs = set()
    for lfn in lfns:
        print(f"  {Path(lfn).name}")
        try:
            pairs = get_run_lumi_pairs(lfn)
            file_pairs[lfn] = pairs
            all_runs.update(r for r, _ in pairs)
        except Exception as e:
            print(f"  ERROR reading {lfn}: {e}")

    if not file_pairs:
        print("ERROR: could not read any custom files.")
        sys.exit(1)

    # --- DAS query (all runs at once) ---------------------------------------
    print(f"\nQuerying DAS for {len(all_runs)} run(s) in {args.dataset}")
    lumi_to_file = build_lumi_to_file_map(args.dataset, all_runs)
    print(f"  {len(lumi_to_file)} (run, lumi) pairs mapped")

    # --- Build per-job specs ------------------------------------------------
    jobs = []
    for lfn, pairs in file_pairs.items():
        central_lfns = sorted({lumi_to_file[(r, l)] for r, l in pairs if (r, l) in lumi_to_file})
        n_missing = sum(1 for r, l in pairs if (r, l) not in lumi_to_file)
        if n_missing:
            print(f"  WARNING: {n_missing} (run,lumi) pairs from {Path(lfn).name} not found in DAS")
        if not central_lfns:
            print(f"  WARNING: no central files found for {Path(lfn).name}, skipping")
            continue
        jobs.append({
            "custom_lfn":  lfn,
            "central_csv": ",".join(central_lfns),
            "output_json": Path(lfn).stem + ".json",  # local filename; condor transfers it back
        })

    print(f"\n{len(jobs)} job(s) to submit")

    # --- Write condor submit file -------------------------------------------
    verify_script  = HERE / "verify_nano.py"
    wrapper_script = HERE / "run_verify.sh"
    submit_path    = Path("verify_condor.sub")

    with open(submit_path, "w") as f:
        f.write(f"""\
universe              = vanilla
executable            = {wrapper_script}
transfer_input_files  = {verify_script}
initialdir            = {results_dir}
output                = {logs_dir}/verify_$(Process).out
error                 = {logs_dir}/verify_$(Process).err
log                   = {logs_dir}/condor.log
use_x509userproxy     = true
request_memory        = 2048
request_cpus          = 1
request_disk          = 2097152
+ProjectName          = "cms"

arguments             = "$(custom_lfn) $(central_csv) $(output_json)"
transfer_output_files = $(output_json)
""")
        for job in jobs:
            f.write(
                f'\ncustom_lfn  = {job["custom_lfn"]}\n'
                f'central_csv = {job["central_csv"]}\n'
                f'output_json = {job["output_json"]}\n'
                f'queue 1\n'
            )

    print(f"Wrote {submit_path}")

    if args.dry_run:
        print("Dry run — not submitting.")
        return

    subprocess.run(["condor_submit", str(submit_path)], check=True)


if __name__ == "__main__":
    main()
