# DLS Pveto PCAS For Trigger-Trimmed NanoAOD

This directory contains the DLS-owned copy of the muon Pveto PocketCoffea
analysis script (PCAS) adapted for the trigger-trimmed disappearing-track custom
NanoAOD.

The important schema decision is intentional:

- PCAS reads central NanoAOD kinematics such as `Muon_pt`, `Muon_eta`, `Jet_pt`,
  and `Jet_eta`.
- PCAS reads custom DLS extras only where central NanoAOD does not already
  provide the needed definition, such as `muon_isTrigMatched`,
  `jet_isTightLepVeto`, `metNoMu_pt`, `metNoMu_phi`, and `trk_*`.
- PCAS does not require old lowercase duplicate kinematic branches.

## Files

```text
dls_pveto_core.py
dls_pveto_cuts.py
dls_pveto_native_workflow.py
dls_pveto_processor.py
analysis_config_pveto_native.py
run_dls_trimmed_nanoaod_pveto.py
export_pveto_json.py
make_dataset_json.py
run_options_local.yaml
datasets/dls_trimmed_nanoaod_smoke.json
```

The direct wrapper is useful for schema validation and simple local checks:

```text
run_dls_trimmed_nanoaod_pveto.py
```

The native PocketCoffea entry point is:

```text
analysis_config_pveto_native.py
```

## Environment On LPC

Use the official PocketCoffea Apptainer image:

```bash
apptainer exec \
  -B /cvmfs:/cvmfs \
  -B /uscms:/uscms \
  -B /uscms_data:/uscms_data \
  /cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-analysis/general/pocketcoffea:lxplus-el9-stable \
  bash
```

Inside the container, use the real `/uscms_data` path for the checkout:

```bash
cd /uscms_data/d3/czheng/CMSSW_15_0_10/src/DisplacedLeptonsSupplement
```

## Direct Smoke Test

Run on the existing DLS trigger-trimmed smoke file:

```bash
python3 CustomNanoAOD/pocketcoffea_pveto/run_dls_trimmed_nanoaod_pveto.py \
  --single-muon CustomNanoAOD/test_outputs/disapptrks_run2022F_muon_skim_max350_dlsfixed2_numEvent350.root \
  --tree Events \
  --layers all \
  --json-output CustomNanoAOD/validation/results/dls_pcas_pveto_smoke.json \
  --output CustomNanoAOD/validation/results/dls_pcas_pveto_smoke.root
```

The current smoke file was built with reduced standard Electron content. If
`Electron_eta` or `Electron_phi` is missing, the direct wrapper fails early with
a message explaining that the DLS NanoAOD must preserve central Electron
coordinates or add a minimal non-duplicate electron-coordinate solution. That
failure is expected for reduced validation files and should not be hidden.

## Native PocketCoffea Smoke Test

```bash
DISAPPTRKS_PVETO_DATASET_JSON=CustomNanoAOD/pocketcoffea_pveto/datasets/dls_trimmed_nanoaod_smoke.json \
pocket-coffea run \
  --cfg CustomNanoAOD/pocketcoffea_pveto/analysis_config_pveto_native.py \
  -o CustomNanoAOD/validation/results/dls_pcas_native_smoke \
  --test \
  --custom-run-options CustomNanoAOD/pocketcoffea_pveto/run_options_local.yaml
```

Export the compact Pveto JSON:

```bash
python3 CustomNanoAOD/pocketcoffea_pveto/export_pveto_json.py \
  CustomNanoAOD/validation/results/dls_pcas_native_smoke/output_all.coffea \
  --output CustomNanoAOD/validation/results/dls_pcas_native_smoke/pveto_summary.json
```

## Trigger-Skim Interpretation

Trigger-trimmed Muon files are acceptable for Pveto counting because the input
file is already restricted to the SingleMuon trigger skim. They are not
acceptable for measuring trigger efficiency denominators; those studies require
unskimmed validation/control output.

The first cutflow label is therefore:

```text
input event kept by SingleMuon trigger skim
```

When `HLT_IsoMu24` is present, PCAS uses it as a diagnostic event mask.
