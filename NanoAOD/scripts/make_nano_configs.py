#!/usr/bin/env python3
"""
Generate custom NanoAOD cmsDriver configs and CRAB3 submission configs
for a list of MiniAOD/NanoAOD dataset pairs.

For each pair the script:
  1. Queries DAS for the config used to produce the central NanoAOD dataset.
  2. Fetches that config and extracts the original cmsDriver command-line options.
  3. Runs cmsDriver.py with our customizations applied, producing a cfg.py.
  4. Writes a CRAB3 config that submits the cfg.py against the MiniAOD dataset.
     Data and MC configs differ: data gets a golden lumi JSON and LumiBased splitting.

A submit_all.sh is also written to the output directory.

Input JSON format:
    [
      {
        "miniaod": "/PrimaryDataset/Run2018A-UL2018_MiniAODv2_NanoAODv9-v1/MINIAOD",
        "nanoaod": "/PrimaryDataset/Run2018A-UL2018_MiniAODv2_NanoAODv9-v1/NANOAOD"
      },
      ...
    ]

Usage (inside a CMSSW environment):
    python3 NanoAOD/scripts/make_nano_configs.py datasets.json [--output-dir configs/]
"""

import argparse
import http.client
import json
import os
import re
import shlex
import ssl
import subprocess
import sys
from urllib.parse import urlparse

CUSTOM_CUSTOMIZE = (
    "DisplacedLeptonsSupplement/NanoAOD/custom_displaced_leptons_cff.PrepDisplacedLeptonsNanoAOD"
)
CUSTOM_COMMAND = "process.MessageLogger.cerr.FwkReport.reportEvery = 1000"

# Golden lumi JSON paths for each run year.
# Run2 UL paths are on AFS; update Run3 entries when known.
GOLDEN_JSONS = {
    2016: (
        "/afs/cern.ch/cms/CAF/CMSCOMM/COMM_DQM/certification/Collisions16/13TeV/Legacy_2016/Cert_271036-284044_13TeV_Legacy2016_Collisions16_JSON.txt"
    ),
    2017: (
        "/afs/cern.ch/cms/CAF/CMSCOMM/COMM_DQM/certification/Collisions17/13TeV/Legacy_2017/Cert_294927-306462_13TeV_UL2017_Collisions17_JSON.txt"
    ),
    2018: (
        "/afs/cern.ch/cms/CAF/CMSCOMM/COMM_DQM/certification/Collisions18/13TeV/Legacy_2018/Cert_314472-325175_13TeV_Legacy2018_Collisions18_JSON.txt"
    ),
    # Run3 — update these paths once the golden JSONs are finalised:
    2022: "https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions22/Cert_Collisions2022_355100_362760_Golden.json",
    2023: "<TODO: Run3 2023 golden JSON path>",
    2024: "<TODO: Run3 2024 golden JSON path>",
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
config.JobType.outputFiles = ['nano.root']   # must match --fileout in cmsDriver

config.Data.inputDataset = '{input_dataset}'
config.Data.inputDBS = 'global'
config.Data.splitting = '{splitting}'
config.Data.unitsPerJob = {units_per_job}{lumi_mask_line}
config.Data.publication = False

config.Data.outLFNDirBase = '/store/user/lnestor/customNanoAOD/{era}/'
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
    Works for both data (Run2018A-...) and MC (RunIISummer20UL18...).
    """
    m = re.search(r"UL(\d{2})\b", dataset)
    if m:
        return 2000 + int(m.group(1))
    m = re.search(r"Run(\d{4})", dataset)
    if m:
        return int(m.group(1))
    raise ValueError(f"Could not determine run year from dataset path: {dataset}")


def get_config_url(nanoaod_dataset: str) -> str:
    """Return the URL of the config that produced the given NanoAOD dataset."""
    cmd = (
        f'dasgoclient -query "config dataset={nanoaod_dataset}" -json '
        f"| jq -r '[.[].config[]] | map(select(.idict.byoutputdataset != null)) | .[0].urls[0]'"
    )
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
    url = result.stdout.strip()
    if not url or url == "null":
        raise RuntimeError(f"No config URL returned for NanoAOD dataset: {nanoaod_dataset}")
    return url


def fetch_config_text(url: str) -> str:
    """Fetch a cmsweb URL authenticated with the VOMS proxy certificate."""
    proxy = os.environ.get("X509_USER_PROXY", "")
    if not proxy:
        raise RuntimeError("X509_USER_PROXY is not set; run voms-proxy-init first")

    # Use Python's ssl module (OpenSSL-backed in CMSSW) rather than the
    # system curl, which is NSS-backed on EL7 and cannot parse VOMS proxies.
    ctx = ssl.create_default_context(capath="/etc/grid-security/certificates/")
    ctx.load_cert_chain(proxy)

    parsed = urlparse(url)
    conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, context=ctx)
    conn.request("GET", parsed.path)
    resp = conn.getresponse()
    if resp.status != 200:
        raise RuntimeError("HTTP {} fetching {}".format(resp.status, url))
    return resp.read().decode("utf-8")


def extract_cmsdriver_args(config_text: str) -> str:
    for line in config_text.splitlines():
        if "# with command line options:" in line:
            return line.split("# with command line options:", 1)[1].strip()
    raise ValueError("Could not find '# with command line options:' line in config")


def dataset_short_name(dataset: str) -> str:
    """Return a unique short name incorporating the primary dataset and run era.

    /MuonEG/Run2018C-UL2018_MiniAODv2_GT36-v1/MINIAOD -> MuonEG_Run2018C
    """
    parts = dataset.strip("/").split("/")
    primary = parts[0]
    era = parts[1].split("-")[0] if len(parts) > 1 else ""
    return "{}_{}".format(primary, era) if era else primary


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


def build_cmsdriver_cmd(original_args: str, cfg_path: str, data: bool, short_name: str) -> tuple:
    """
    Apply our customizations to the original cmsDriver args.
    Returns (shell_command_string, input_dataset_string).
    """
    tokens = shlex.split(original_args)

    tokens = _set_arg(tokens, "--python_filename", cfg_path)
    tokens = _set_arg(tokens, "--fileout", "file:nano.root")
    tokens = _set_arg(tokens, "--nThreads", "1")
    tokens = _set_arg(tokens, "--filein", short_name + "_MiniAOD.root")
    tokens = _append_to_arg(tokens, "--customise", CUSTOM_CUSTOMIZE, ",")
    tokens = _append_to_arg(tokens, "--customise_command", CUSTOM_COMMAND, "; ")

    if data:
        tokens = _set_arg(tokens, "--eventcontent", "NANOAOD")

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
    year: int,
    num_cores: int = 1,
) -> None:
    if data:
        splitting = "LumiBased"
        units_per_job = 50
        lumi_json = GOLDEN_JSONS.get(year, f"<TODO: golden JSON for {year}>")
        lumi_mask_line = f"\nconfig.Data.lumiMask = '{lumi_json}'"
        era = f"Run{year}"
    else:
        splitting = "FileBased"
        units_per_job = 1
        lumi_mask_line = ""
        era = f"UL{str(year)[2:]}"  # 2018 -> UL18

    content = CRAB_TEMPLATE.format(
        request_name="{}_customNanoAOD".format(short_name)[:100],
        pset_name=os.path.abspath(cfg_path),
        num_cores=num_cores,
        input_dataset=input_dataset,
        splitting=splitting,
        units_per_job=units_per_job,
        lumi_mask_line=lumi_mask_line,
        era=era,
        output_tag="{}_customNanoAOD".format(short_name),
    )
    with open(crab_path, "w") as f:
        f.write(content)


def process_dataset(miniaod: str, nanoaod: str, output_dir: str) -> tuple:
    """Run the full pipeline for one dataset pair. Returns (cfg_path, crab_path)."""
    short_name = dataset_short_name(miniaod)
    cfg_path = os.path.join(output_dir, f"{short_name}_NANO.py")
    crab_path = os.path.join(output_dir, f"crab_{short_name}.py")
    data = is_data(miniaod)

    try:
        year = detect_year(miniaod)
    except ValueError as e:
        print(f"  WARNING: {e}; year-dependent fields will use placeholders")
        year = 0

    print("  Querying DAS for config URL...")
    url = get_config_url(nanoaod)
    print(f"  URL: {url}")

    print("  Fetching config file...")
    config_text = fetch_config_text(url)

    original_args = extract_cmsdriver_args(config_text)
    cmd, input_dataset, num_cores = build_cmsdriver_cmd(original_args, cfg_path, data, short_name)

    print("  Running cmsDriver.py...")
    print(f"    {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
    subprocess.run(cmd, shell=True, check=True)

    # Central configs use _placeholder_.root for --filein; always use the
    # actual miniaod argument as the CRAB input dataset.
    if input_dataset and input_dataset.startswith("/"):
        print("  Input dataset (crab): {}".format(input_dataset))
    else:
        input_dataset = miniaod
        print("  Input dataset (crab): {} (from JSON)".format(input_dataset))

    write_crab_config(crab_path, cfg_path, short_name, input_dataset, data, year, num_cores)
    kind = "data" if data else "MC"
    print(f"  CRAB config ({kind}, {year}): {crab_path}")

    return cfg_path, crab_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "datasets_file",
        help="JSON file with a list of {miniaod, nanoaod} dataset pairs",
    )
    parser.add_argument(
        "--output-dir", "-o", default="configs",
        help="Directory for generated config files (default: configs/)",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    with open(args.datasets_file) as f:
        pairs = json.load(f)

    if not pairs:
        sys.exit("No dataset pairs found in input file.")

    print(f"Processing {len(pairs)} dataset pair(s) -> {args.output_dir}/\n")

    crab_configs = []
    failed = []
    for pair in pairs:
        miniaod = pair["miniaod"]
        nanoaod = pair["nanoaod"]
        print(f"[{miniaod}]")
        try:
            cfg_path, crab_path = process_dataset(miniaod, nanoaod, args.output_dir)
            crab_configs.append(crab_path)
            print(f"  OK: {cfg_path}\n")
        except Exception as exc:
            print(f"  FAILED: {exc}\n", file=sys.stderr)
            failed.append(miniaod)

    submit_script = os.path.join(args.output_dir, "submit_all.sh")
    with open(submit_script, "w") as f:
        f.write("#!/bin/bash\nset -e\n\n")
        for p in crab_configs:
            f.write(f"crab submit {p}\n")
    os.chmod(submit_script, 0o755)
    print(f"Wrote submit script: {submit_script}")

    if failed:
        print(f"\nFailed datasets ({len(failed)}):")
        for d in failed:
            print(f"  {d}")
        sys.exit(1)


if __name__ == "__main__":
    main()
