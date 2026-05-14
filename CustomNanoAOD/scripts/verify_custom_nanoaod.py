import argparse
import awkward as ak
import json
import numpy as np
import os
import subprocess
import tempfile
import uproot

DEFAULT_BRANCHES = [
    "nMuon",
    "Muon_pt", "Muon_eta", "Muon_phi",
    "Muon_dxy", "Muon_dz", "Muon_dxyErr", "Muon_dzErr",
    "Muon_charge",
    "nElectron",
    "Electron_pt", "Electron_eta", "Electron_phi",
    "Electron_dxy", "Electron_dz",
]

DISPLACED_BRANCHES = [
    "DisplacedMuon_pt", "DisplacedMuon_eta", "DisplacedMuon_phi",
    "DisplacedMuon_dxy", "DisplacedMuon_dxyErr",
    "DisplacedMuon_dz", "DisplacedMuon_dzErr",
]

FLOAT_RTOL = 1e-2
MAX_ERROR_MSGS_PER_BRANCH = 5

XROOTD_PREFIX = "root://cmsxrootd.fnal.gov/"
EOS_PREFIX = "root://cmseos.fnal.gov/"

_EXTRACT_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../python/extract_cfg.py")

def load_events(path, branches):
    full_path = path
    # TODO: distinguish between eos and xrootd required
    if path.startswith("/store"):
        full_path = XROOTD_PREFIX + path

    with uproot.open(full_path) as f:
        tree = f["Events"]
        available_branches = set(tree.keys())
        to_load = ["run", "luminosityBlock", "event"] + [b for b in branches if b in available_branches]
        arrays = tree.arrays(to_load, library="ak")

    return arrays, available_branches


def das_query(query):
    result = subprocess.run(
        ["dasgoclient", "--query", query, "--json"],
        capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def get_central_files(dataset, custom_events):
    runs = set(int(run) for run in ak.to_list(custom_events.run))
    lumi_to_file_map = {}

    for run in sorted(runs):
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
                lumi_to_file_map[(run, int(lumi))] = path

    files = set()
    missing = []
    for run, lumi in zip(ak.to_list(custom_events.run), ak.to_list(custom_events.luminosityBlock)):
        central_file = lumi_to_file_map.get((int(run), int(lumi)))
        if central_file is not None:
            files.add(central_file)
        else:
            missing.append((int(run), int(lumi)))

    return list(files), missing


def do_values_match(vals1, vals2):
    a, b = ak.to_list(vals1), ak.to_list(vals2)
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


def compare_branch_presence(custom_branches, central_branches):
    return {
        "extra_in_custom": sorted(custom_branches - central_branches),
        "extra_in_central": sorted(central_branches - custom_branches),
    }


def extract_collection(branch):
    if '_' in branch:
        return branch.split('_')[0]
    if branch.startswith('n') and len(branch) > 1 and branch[1].isupper():
        return branch[1:]
    return None


def compare_collection_presence(custom_branches, central_branches):
    custom_coll = {extract_collection(b) for b in custom_branches} - {None}
    central_coll = {extract_collection(b) for b in central_branches} - {None}
    return {
        "missing_from_custom": sorted(central_coll - custom_coll),
        "missing_from_central": sorted(custom_coll - central_coll),
    }


def compare_branches(custom_events, central_events, to_compare):
    n_not_in_central = 0
    n_compared = 0
    n_errors = {b: 0 for b in to_compare}
    error_msgs = {b: [] for b in to_compare}

    central_indices = {
        (int(run), int(lumi), int(event)): idx
        for idx, (run, lumi, event) in enumerate(
            zip(ak.to_list(central_events.run),
                ak.to_list(central_events.luminosityBlock),
                ak.to_list(central_events.event)
            )
        )
    }

    for custom_event in custom_events:
        run = int(custom_event.run)
        lumi = int(custom_event.luminosityBlock)
        event = int(custom_event.event)

        central_idx = central_indices.get((run, lumi, event))

        if central_idx is None:
            n_not_in_central += 1
            continue
        n_compared += 1

        for branch in to_compare:
            ok, msg = do_values_match(custom_event[branch], central_events[branch][central_idx])

            if not ok:
                n_errors[branch] += 1
                if len(error_msgs[branch]) < MAX_ERROR_MSGS_PER_BRANCH:
                    error_msgs[branch].append(f"run={run} lumi={lumi} event={event}: {msg}")

    return {
        "n_events_compared": n_compared,
        "n_events_not_in_central": n_not_in_central,
        "branches": {
            b: {
                "status": "pass" if n_errors[b] == 0 else "fail",
                "n_mismatches": n_errors[b],
                "errors": error_msgs[b],
            }
            for b in to_compare
        },
    }

def extract_mini_info(files, cfg_path=None):
    if cfg_path is None:
        cfg_path = _EXTRACT_CFG
    arrays = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, f in enumerate(files):
            input_path = (XROOTD_PREFIX + f) if f.startswith("/store") else f
            output_path = os.path.join(tmpdir, f"extract_{i}.root")

            print(f"\nExtracting displaced muons from: {f}")
            try:
                subprocess.run(
                    ["cmsRun", cfg_path, f"inputFiles={input_path}", f"outputFile={output_path}"],
                    check=True, capture_output=True, text=True,
                )
            except subprocess.CalledProcessError as e:
                print(e.stderr)
                raise

            with uproot.open(output_path) as froot:
                arrays.append(froot["extract/DisplacedMuons"].arrays(library="ak"))

    events = ak.concatenate(arrays) if len(arrays) > 1 else arrays[0]
    print(f"  Extracted {len(events)} events")
    return events


def compare_mini_branches():
    # for every event in custom, find the corresponding event in central
    # Compare all branches and make sure they match
    pass


def _group_branches_by_collection(branches):
    groups = {}
    for b in sorted(branches):
        coll = extract_collection(b) or b
        groups.setdefault(coll, []).append(b)
    return groups


def _print_branch_presence(label, branches, verbose):
    if not branches:
        return
    groups = _group_branches_by_collection(branches)
    print(f"\n{label} ({len(branches)} branches):")
    for coll, coll_branches in sorted(groups.items()):
        n = len(coll_branches)
        print(f"  {coll} ({n} {'branch' if n == 1 else 'branches'})")
        if verbose:
            for b in coll_branches:
                print(f"    {b}")


def _print_comparison(label, comparison, verbose):
    branches = comparison["branches"]
    n_pass = sum(1 for r in branches.values() if r["status"] == "pass")
    n_total = len(branches)
    n_events = comparison["n_events_compared"]
    n_missing = comparison["n_events_not_in_central"]

    status = "all passed" if n_pass == n_total else f"{n_total - n_pass} failed"
    missing_note = f", {n_missing} not in central" if n_missing else ""
    print(f"\n{label}  {n_pass}/{n_total} branches {status}  ({n_events} events{missing_note})")

    for branch, result in branches.items():
        is_fail = result["status"] == "fail"
        if not is_fail and not verbose:
            continue
        line = f"  {'FAIL' if is_fail else 'PASS'} {branch}"
        if result["n_mismatches"]:
            line += f"  ({result['n_mismatches']} mismatches)"
        print(line)
        if verbose:
            for err in result["errors"]:
                print(f"       {err}")


def print_results(results, verbose=False):
    bp = results["branch_presence"]
    _print_branch_presence("Extra branches in custom NanoAOD", bp["extra_in_custom"], verbose)
    _print_branch_presence("Extra branches in central NanoAOD", bp["extra_in_central"], verbose)
    if not bp["extra_in_custom"] and not bp["extra_in_central"]:
        print("\nNo extra branches in either NanoAOD file")

    cp = results["collection_presence"]
    missing_lines = []
    if cp["missing_from_custom"]:
        missing_lines.append(f"  missing from custom ({len(cp['missing_from_custom'])}): {', '.join(cp['missing_from_custom'])}")
    if cp["missing_from_central"]:
        missing_lines.append(f"  missing from central ({len(cp['missing_from_central'])}): {', '.join(cp['missing_from_central'])}")
    if missing_lines:
        print("\nCollections:")
        for line in missing_lines:
            print(line)

    _print_comparison("NanoAOD:", results["nano_comparison"], verbose)

    if results.get("mini_comparison"):
        _print_comparison("MiniAOD displaced muons:", results["mini_comparison"], verbose)

    print()


def save_results_json(path, results):
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {path}")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--branches", nargs="+", default=DEFAULT_BRANCHES,
        metavar="BRANCH",
        help="NanoAOD branches to compare against central. Defaults to a standard set of muon/electron branches.",
    )
    common.add_argument(
        "--output-json", metavar="PATH",
        help="Write full results (branch presence, comparison results, error details) as JSON to PATH.",
    )
    common.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print individual branch names and per-event mismatch details. Without this flag only failures are shown.",
    )
    common.add_argument(
        "--extract-cfg", metavar="PATH", default=None,
        help=(
            "Path to extract_cfg.py used for MiniAOD displaced-muon extraction. "
            "Defaults to ../python/extract_cfg.py relative to this script. "
            "Override when running in a condor job where the script-relative path is wrong."
        ),
    )

    parser = argparse.ArgumentParser(
        description=(
            "Verify a custom NanoAOD file against central NanoAOD and optionally against MiniAOD.\n\n"
            "Checks that branches present in both files have matching values event-by-event, "
            "and reports any extra or missing collections. If the custom file contains DisplacedMuon "
            "branches and MiniAOD is provided, those branches are also compared against values "
            "extracted directly from MiniAOD via cmsRun."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Look up central files automatically via DAS\n"
            "  verify_custom_nanoaod.py /path/to/custom.root standalone \\\n"
            "      --nanoaod-dataset /Dataset/Run3/NANOAOD \\\n"
            "      --miniaod-dataset /Dataset/Run3/MINIAOD\n\n"
            "  # Supply central files directly (e.g. from a batch job)\n"
            "  verify_custom_nanoaod.py /path/to/custom.root batch \\\n"
            "      --nanoaod-filenames /store/data/.../nano.root \\\n"
            "      --miniaod-filenames /store/data/.../mini.root\n\n"
            "  # Verbose output + save JSON results\n"
            "  verify_custom_nanoaod.py /path/to/custom.root standalone \\\n"
            "      --nanoaod-dataset /Dataset/Run3/NANOAOD \\\n"
            "      --verbose --output-json results.json"
        ),
    )
    parser.add_argument(
        "custom_nanoaod",
        help="Local path or LFN (starting with /store) of the custom NanoAOD file to verify.",
    )
    subparser = parser.add_subparsers(dest="mode", required=True)

    standalone = subparser.add_parser(
        "standalone",
        parents=[common],
        help="Look up central files automatically from DAS using the provided dataset names.",
        description=(
            "Automatically queries DAS to find the central NanoAOD (and optionally MiniAOD) files "
            "that contain the same run/lumi sections as the custom NanoAOD, then runs the comparison."
        ),
    )
    standalone.add_argument(
        "--nanoaod-dataset", required=True, metavar="DATASET",
        help="DAS dataset path for the central NanoAOD (e.g. /Dataset/Run3/NANOAOD).",
    )
    standalone.add_argument(
        "--miniaod-dataset", metavar="DATASET",
        help=(
            "DAS dataset path for the central MiniAOD (e.g. /Dataset/Run3/MINIAOD). "
            "Required to compare DisplacedMuon branches, which are not present in central NanoAOD."
        ),
    )

    batch = subparser.add_parser(
        "batch",
        parents=[common],
        help="Supply central file paths directly, bypassing DAS lookup.",
        description=(
            "Use when the central files are already known (e.g. passed in from a batch job). "
            "Skips the DAS query and loads the provided files directly."
        ),
    )
    batch.add_argument(
        "--nanoaod-filenames", nargs="+", required=True, metavar="FILE",
        help="One or more central NanoAOD file paths or LFNs.",
    )
    batch.add_argument(
        "--miniaod-filenames", nargs="+", metavar="FILE",
        help=(
            "One or more central MiniAOD file paths or LFNs. "
            "Required to compare DisplacedMuon branches."
        ),
    )

    args = parser.parse_args()

    print(f"\nLoading custom NanoAOD file: {args.custom_nanoaod}")
    custom_events, custom_branches = load_events(args.custom_nanoaod, args.branches + DISPLACED_BRANCHES)
    print(f"  Loaded {len(custom_events)} events")

    custom_missing = [b for b in args.branches if b not in custom_branches]
    if custom_missing:
        print(f"  WARNING: branches absent from custom NanoAOD (skipped): {custom_missing}")

    if args.mode == "standalone":
        central_nano_files, missing_nano_run_lumis = get_central_files(args.nanoaod_dataset, custom_events)
        central_mini_files, missing_mini_run_lumis = get_central_files(args.miniaod_dataset, custom_events) if args.miniaod_dataset else ([], [])
    else:
        central_nano_files = args.nanoaod_filenames
        central_mini_files = args.miniaod_filenames if args.miniaod_filenames else []

    central_file_events = []
    for f in central_nano_files:
        print(f"\nLoading central NanoAOD file: {f}")
        events, central_branches = load_events(f, args.branches)
        central_file_events.append(events)
        print(f"  Loaded {len(events)} events")

    # TODO: Can we narrow this down to just the events in custom nanoaod?
    central_events = (
        ak.accumulate(central_file_events)
        if len(central_file_events) > 1
        else central_file_events[0]
    )

    central_missing = [b for b in args.branches if b not in central_branches]
    if central_missing:
        print(f"  WARNING: branches absent from central NanoAOD (skipped): {central_missing}")

    to_compare = [b for b in args.branches if b in custom_branches and b in central_branches]

    results = {
        "custom_nanoaod": args.custom_nanoaod,
        "central_nano_files": central_nano_files,
        "branches_requested": args.branches,
        "branch_presence": compare_branch_presence(custom_branches, central_branches),
        "collection_presence": compare_collection_presence(custom_branches, central_branches),
        "nano_comparison": compare_branches(custom_events, central_events, to_compare),
    }

    custom_has_displaced_info = any("DisplacedMuon" in b for b in custom_branches)
    if custom_has_displaced_info and central_mini_files:
        mini_events = extract_mini_info(central_mini_files, cfg_path=args.extract_cfg)
        results["mini_comparison"] = compare_branches(custom_events, mini_events, DISPLACED_BRANCHES)
    elif custom_has_displaced_info:
        print("  WARNING: custom NanoAOD has displaced muon branches but no MiniAOD was provided — skipping displaced muon comparison")
    elif central_mini_files:
        print("  WARNING: MiniAOD was provided but custom NanoAOD has no displaced muon branches — skipping displaced muon comparison")

    print_results(results, verbose=args.verbose)

    if args.output_json:
        save_results_json(args.output_json, results)



if __name__ == "__main__":
    main()
