#!/usr/bin/env python3
"""
Generate custom NanoAOD cmsDriver configs and CRAB3 submission configs
for a list of MiniAOD datasets.

For each dataset the script:
  1. Looks up the conditions and era for the dataset's campaign from
     CAMPAIGN_ARGS and constructs the base cmsDriver command directly,
     without querying DAS for a central config.
  2. Runs cmsDriver.py with our customizations applied, producing a cfg.py.
  3. Writes a CRAB3 config that submits the cfg.py against the MiniAOD dataset.
     Data and MC configs differ: data gets a golden lumi JSON and LumiBased
     splitting.

A submit_all.sh is also written to the output directory.

Input file format: one MiniAOD dataset path per line.

Usage (inside a CMSSW environment):
    python3 make_nano_configs.py datasets.txt [--output-dir configs/]

To add support for a new campaign, add an entry to CAMPAIGN_ARGS.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys

CUSTOMIZE_OPTIONS = {
    "displaced-leptons": (
        "DisplacedLeptonsSupplement/CustomNanoAOD/custom_displaced_leptons_cff.PrepDisplacedLeptonsNanoAOD"
    ),
    "disapptrks": (
        "DisplacedLeptonsSupplement/CustomNanoAOD/custom_displaced_leptons_cff.PrepDisplacedLeptonsDisappTrksNanoAOD"
    ),
    "disapptrks-met-skim": (
        "DisplacedLeptonsSupplement/CustomNanoAOD/custom_displaced_leptons_cff.PrepDisplacedLeptonsDisappTrksNanoAOD_METSkim"
    ),
    "disapptrks-muon-skim": (
        "DisplacedLeptonsSupplement/CustomNanoAOD/custom_displaced_leptons_cff.PrepDisplacedLeptonsDisappTrksNanoAOD_MuonSkim"
    ),
    "disapptrks-egamma-skim": (
        "DisplacedLeptonsSupplement/CustomNanoAOD/custom_displaced_leptons_cff.PrepDisplacedLeptonsDisappTrksNanoAOD_EGammaSkim"
    ),
}
DEFAULT_CUSTOMIZE = "displaced-leptons"
CUSTOM_COMMAND = (
    "process.add_(cms.Service('InitRootHandlers', EnableIMT = cms.untracked.bool(False))); "
    "process.MessageLogger.cerr.FwkReport.reportEvery = 1000"
)

# Keyed by MC campaign prefix (the leading part of the middle path segment
# before "MiniAOD") or "data_{year}" for data.
# "label" is used as the subdirectory in the CRAB output LFN.
CAMPAIGN_ARGS = {
    # Run 3 2024 MC
    "RunIII2024Summer24": {
        "conditions": "150X_mcRun3_2024_realistic_v2",
        "era": "Run3_2024",
        "label": "MC_2024",
    },
    # Run 3 2024 data
    "data_2024": {
        "conditions": "150X_dataRun3_v2",
        "era": "Run3_2024",
        "label": "Run2024",
    },
    # Run 3 2023 -- TODO: fill in correct conditions
    "RunIII2023Summer23": {
        "conditions": "<TODO: 2023 MC conditions>",
        "era": "Run3_2023",
        "label": "MC_2023",
    },
    "data_2023": {
        "conditions": "<TODO: 2023 data conditions>",
        "era": "Run3_2023",
        "label": "Run2023",
    },
    # Run 3 2022
    "Run3Summer22": {
        "conditions": "<TODO: 2022 MC conditions>",
        "era": "Run3",
        "label": "MC_2022",
    },
    "data_2022": {
        "conditions": "124X_dataRun3_v15",
        "era": "Run3",
        "label": "Run2022",
    },
}

RUN2022_PRE_EE_MUON_TRIGGER_FILTER = "hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered0p08"

# Golden lumi JSON paths for each run year.
GOLDEN_JSONS = {
    # These are my best guesses for the JSONs for the run 2 datasets that were used to create the analysis note
    2016: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions16/13TeV/ReReco/Final/Cert_271036-284044_13TeV_ReReco_07Aug2017_Collisions16_JSON.txt",
    2017: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions18/13TeV/ReReco/Cert_314472-325175_13TeV_17SeptEarlyReReco2018ABC_PromptEraD_Collisions18_JSON.txt",
    2018: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions17/13TeV/ReReco/Cert_294927-306462_13TeV_EOY2017ReReco_Collisions17_JSON_v1.txt",
    # Below are ultra-legacy. Saving them in case they are needed
    # 2016: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions16/13TeV/Legacy_2016/Cert_271036-284044_13TeV_Legacy2016_Collisions16_JSON.txt",
    # 2017: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions17/13TeV/Legacy_2017/Cert_294927-306462_13TeV_UL2017_Collisions17_GoldenJSON.txt",
    # 2018: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions18/13TeV/Legacy_2018/Cert_314472-325175_13TeV_Legacy2018_Collisions18_JSON.txt",
    2022: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions22/Cert_Collisions2022_355100_362760_Golden.json",
    2023: "<TODO: Run3 2023 golden JSON path>",
    2024: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions24/Cert_Collisions2024_378981_386951_Golden.json",
}

CRAB_TEMPLATE = """\
from CRABClient.UserUtilities import config

config = config()

config.General.requestName = '{request_name}'
config.General.workArea = 'crab_projects'
config.General.transferOutputs = True
config.General.transferLogs = True

config.JobType.pluginName = 'Analysis'
config.JobType.psetName = '{pset_name}'
config.JobType.numCores = {num_cores}
config.JobType.maxMemoryMB = 3000
config.JobType.outputFiles = ['nano.root']   # must match --fileout in cmsDriver

config.Data.inputDataset = '{input_dataset}'
config.Data.inputDBS = 'global'
config.Data.splitting = '{splitting}'
config.Data.unitsPerJob = {units_per_job}{lumi_mask_line}
config.Data.publication = False

config.Data.outLFNDirBase = '{out_lfn_dir_base}/{label}/'
config.Data.outputDatasetTag = '{output_tag}'

config.Site.storageSite = 'T3_US_FNALLPC'
"""


def is_data(dataset: str) -> bool:
    """True if the dataset tier is MINIAOD (real data), False for MINIAODSIM (MC)."""
    tier = dataset.strip("/").split("/")[-1]
    return tier == "MINIAOD"


def detect_year(dataset: str) -> int:
    """
    Extract the run year from a dataset path.
    Works for data (Run2024C-...), Run 2 MC (RunIISummer20UL18...),
    and Run 3 MC (RunIII2024Summer24...).
    """
    m = re.search(r"UL(\d{2})\b", dataset)
    if m:
        return 2000 + int(m.group(1))
    m = re.search(r"RunIII(\d{4})", dataset)
    if m:
        return int(m.group(1))
    m = re.search(r"Run(\d{4})", dataset)
    if m:
        return int(m.group(1))
    raise ValueError(f"Could not determine run year from dataset path: {dataset}")


def detect_campaign(dataset: str, data: bool) -> str:
    """Return the CAMPAIGN_ARGS key for the given dataset."""
    if data:
        year = detect_year(dataset)
        return f"data_{year}"
    middle = dataset.strip("/").split("/")[1]
    for key in CAMPAIGN_ARGS:
        if middle.startswith(key):
            return key
    raise ValueError(
        f"No entry in CAMPAIGN_ARGS matches dataset: {dataset}\n"
        f"  Middle segment: {middle}\n"
        f"  Add the campaign to CAMPAIGN_ARGS to proceed."
    )


def build_base_cmsdriver_args(dataset: str, data: bool) -> str:
    """Return the base cmsDriver argument string for the given dataset's campaign."""
    campaign = detect_campaign(dataset, data)
    cfg = CAMPAIGN_ARGS[campaign]
    conditions = cfg["conditions"]
    era = cfg["era"]
    mc_or_data = "--data" if data else "--mc"
    datatier = "NANOAOD" if data else "NANOAODSIM"
    return (
        f"NANO {mc_or_data} --conditions {conditions} --era {era} "
        f"--datatier {datatier} --eventcontent {datatier} "
        f"--step NANO --scenario pp --no_exec "
        f"--customise Configuration/DataProcessing/Utils.addMonitoring"
    )


def get_first_das_file(dataset: str) -> str:
    """Return the LFN of the first file in a DAS dataset."""
    cmd = f'dasgoclient -query "file dataset={dataset}" -json | jq -r ".[0].file[0].name"'
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
    path = result.stdout.strip()
    if not path or path == "null":
        raise RuntimeError(f"No files found for dataset: {dataset}")
    return path


def fetch_test_file(miniaod: str, dest_path: str) -> None:
    """xrdcp the first file of the MiniAOD dataset to dest_path."""
    lfn = get_first_das_file(miniaod)
    xrd_url = f"root://cmsxrootd.fnal.gov/{lfn}"
    print(f"  Fetching test file: {xrd_url}")
    subprocess.run(["xrdcp", xrd_url, dest_path], check=True)
    print(f"  Saved to: {dest_path}")


def dataset_short_name(dataset: str) -> str:
    """Return a unique short name incorporating the primary dataset and run era,
    with a reprocessing version suffix when present in the processing tag (data only).

    /MuonEG/Run2024I-MINIv6NANOv15-v2/MINIAOD    -> MuonEG_Run2024I
    /MuonEG/Run2024I-MINIv6NANOv15_v2-v2/MINIAOD  -> MuonEG_Run2024I_v2
    """
    parts = dataset.strip("/").split("/")
    primary = parts[0]
    if len(parts) <= 1:
        return primary
    tier = parts[-1]
    segments = parts[1].split("-")
    era = segments[0]
    suffix = ""
    if tier == "MINIAOD" and len(segments) > 1:
        m = re.search(r"(_v\d+)$", segments[1])
        if m:
            suffix = m.group(1)
    return "{}_{}{}".format(primary, era, suffix)


def _set_arg(tokens: list, flag: str, value: str) -> list:
    tokens = list(tokens)
    for i, t in enumerate(tokens):
        if t == flag and i + 1 < len(tokens):
            tokens[i + 1] = value
            return tokens
    return tokens + [flag, value]


def _append_to_arg(tokens: list, flag: str, value: str, sep: str = ",") -> list:
    tokens = list(tokens)
    for i, t in enumerate(tokens):
        if t == flag and i + 1 < len(tokens):
            tokens[i + 1] = tokens[i + 1] + sep + value
            return tokens
    return tokens + [flag, value]


def _get_arg(tokens: list, flag: str):
    for i, t in enumerate(tokens):
        if t == flag and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def _sanitize_label(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", label).strip("_")


def _extra_disapptrks_customise_command(dataset: str, customize: str) -> str:
    """Return dataset-specific overrides for disappTrks custom NanoAOD configs."""
    commands = []
    if customize.startswith("disapptrks"):
        commands.append(
            "from DisplacedLeptonsSupplement.CustomNanoAOD.custom_displaced_leptons_cff "
            "import ApplyDisappTrksRun3MiniAODCompatibility; "
            "process = ApplyDisappTrksRun3MiniAODCompatibility(process)"
        )
    if customize != "disapptrks-muon-skim":
        return "; ".join(commands)
    if re.search(r"^/Muon/Run2022[CD]-", dataset):
        commands.append(
            "process.disappTrkTable.triggerFilterName = "
            "cms.string('{}')".format(RUN2022_PRE_EE_MUON_TRIGGER_FILTER)
        )
    return "; ".join(commands)


def build_cmsdriver_cmd(original_args: str, cfg_path: str, data: bool, short_name: str, customize: str, dataset: str) -> tuple:
    """
    Apply our customizations to the base cmsDriver args.
    Returns (shell_command_string, input_dataset_string, num_cores).
    """
    tokens = shlex.split(original_args)

    tokens = _set_arg(tokens, "--python_filename", cfg_path)
    tokens = _set_arg(tokens, "--fileout", "file:nano.root")
    tokens = _set_arg(tokens, "--nThreads", "1")
    tokens = _set_arg(tokens, "--filein", "file:" + short_name + "_MiniAOD.root")
    tokens = _set_arg(tokens, "--number", "5000")
    tokens = _set_arg(tokens, "--step", "NANO")
    tokens = _append_to_arg(tokens, "--customise", CUSTOMIZE_OPTIONS[customize], ",")
    tokens = _append_to_arg(tokens, "--customise_command", CUSTOM_COMMAND, "; ")
    extra_command = _extra_disapptrks_customise_command(dataset, customize)
    if extra_command:
        tokens = _append_to_arg(tokens, "--customise_command", extra_command, "; ")
    tokens = _set_arg(tokens, "--eventcontent", "NANOAOD" if data else "NANOAODSIM")

    filein = _get_arg(tokens, "--filein") or ""
    input_dataset = filein.removeprefix("dbs:") if filein.startswith("dbs:") else filein
    num_cores = int(_get_arg(tokens, "--nThreads") or 1)

    cmd = "cmsDriver.py " + " ".join(shlex.quote(t) for t in tokens)
    return cmd, input_dataset, num_cores


def write_crab_config(
    crab_path: str,
    cfg_path: str,
    short_name: str,
    input_dataset: str,
    data: bool,
    dataset: str,
    num_cores: int = 1,
    out_lfn_dir_base: str = "/store/user/lnestor/customNanoAOD",
) -> None:
    year = detect_year(dataset)
    campaign = detect_campaign(dataset, data)
    label = CAMPAIGN_ARGS[campaign]["label"]

    if data:
        splitting = "LumiBased"
        units_per_job = 75
        lumi_json = GOLDEN_JSONS.get(year, f"<TODO: golden JSON for {year}>")
        lumi_mask_line = f"\nconfig.Data.lumiMask = '{lumi_json}'"
    else:
        splitting = "FileBased"
        units_per_job = 25
        lumi_mask_line = ""

    content = CRAB_TEMPLATE.format(
        request_name="{}_customNanoAOD".format(short_name)[:100],
        pset_name=os.path.basename(cfg_path),
        num_cores=num_cores,
        input_dataset=input_dataset,
        splitting=splitting,
        units_per_job=units_per_job,
        lumi_mask_line=lumi_mask_line,
        label=label,
        output_tag="{}_customNanoAOD".format(short_name),
        out_lfn_dir_base=out_lfn_dir_base.rstrip("/"),
    )
    with open(crab_path, "w") as f:
        f.write(content)


def process_dataset(
    miniaod: str,
    output_dir: str,
    fetch_test: bool = False,
    customize: str = DEFAULT_CUSTOMIZE,
    out_lfn_dir_base: str = "/store/user/lnestor/customNanoAOD",
) -> tuple:
    """Run the full pipeline for one dataset. Returns (cfg_path, crab_path)."""
    short_name = dataset_short_name(miniaod)
    cfg_stem = short_name
    if customize != DEFAULT_CUSTOMIZE:
        cfg_stem = "{}_{}".format(short_name, _sanitize_label(customize))
    cfg_path = os.path.join(output_dir, f"{cfg_stem}_NANO.py")
    crab_path = os.path.join(output_dir, f"crab_{cfg_stem}.py")
    data = is_data(miniaod)

    base_args = build_base_cmsdriver_args(miniaod, data)
    cmd, input_dataset, num_cores = build_cmsdriver_cmd(base_args, cfg_path, data, short_name, customize, miniaod)

    print("  Running cmsDriver.py...")
    print(f"    {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
    subprocess.run(cmd, shell=True, check=True)

    input_dataset = miniaod
    print("  Input dataset (crab): {}".format(input_dataset))

    write_crab_config(
        crab_path,
        cfg_path,
        cfg_stem,
        input_dataset,
        data,
        miniaod,
        num_cores,
        out_lfn_dir_base=out_lfn_dir_base,
    )
    kind = "data" if data else "MC"
    year = detect_year(miniaod)
    print(f"  CRAB config ({kind}, {year}): {crab_path}")

    if fetch_test:
        test_file_path = os.path.join(output_dir, f"{short_name}_MiniAOD.root")
        print("  Fetching test MiniAOD file...")
        fetch_test_file(miniaod, test_file_path)

    return cfg_path, crab_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "datasets_file",
        help="Text file with one MiniAOD dataset path per line",
    )
    parser.add_argument(
        "--output-dir", "-o", default="configs",
        help="Directory for generated config files (default: configs/)",
    )
    parser.add_argument(
        "--fetch-test-file", action="store_true",
        help="xrdcp the first MiniAOD file from each dataset into the output directory so you can run cmsRun immediately",
    )
    parser.add_argument(
        "--customize",
        choices=sorted(CUSTOMIZE_OPTIONS),
        default=DEFAULT_CUSTOMIZE,
        help="NanoAOD customization to apply (default: %(default)s)",
    )
    parser.add_argument(
        "--out-lfn-dir-base",
        default="/store/user/lnestor/customNanoAOD",
        help="CRAB output LFN base. Use /store/group/lpcdisapptrks/CollinTest for large disTk validation tests.",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    with open(args.datasets_file) as f:
        datasets = [line.strip() for line in f if line.strip()]

    if not datasets:
        sys.exit("No datasets found in input file.")

    print(f"Processing {len(datasets)} dataset(s) -> {args.output_dir}/\n")

    crab_configs = []
    failed = []
    for miniaod in datasets:
        print(f"[{miniaod}]")
        try:
            cfg_path, crab_path = process_dataset(
                miniaod,
                args.output_dir,
                fetch_test=args.fetch_test_file,
                customize=args.customize,
                out_lfn_dir_base=args.out_lfn_dir_base,
            )
            crab_configs.append(crab_path)
            print(f"  OK: {cfg_path}\n")
        except Exception as exc:
            print(f"  FAILED: {exc}\n", file=sys.stderr)
            failed.append(miniaod)

    submit_script = os.path.join(args.output_dir, "submit_all.sh")
    with open(submit_script, "w") as f:
        f.write("#!/bin/bash\nset -e\n\n")
        f.write('SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n')
        f.write('cd "$SCRIPT_DIR"\n\n')
        for p in crab_configs:
            f.write(f"crab submit {os.path.basename(p)}\n")
    os.chmod(submit_script, 0o755)
    print(f"Wrote submit script: {submit_script}")

    if failed:
        print(f"\nFailed datasets ({len(failed)}):")
        for d in failed:
            print(f"  {d}")
        sys.exit(1)


if __name__ == "__main__":
    main()
