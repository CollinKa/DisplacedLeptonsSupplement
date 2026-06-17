# DLS Trigger-Trimmed NanoAOD, PCAS, and 2022 Muon C/D CRAB Path

This note documents the DLS-owned Pveto PCAS copy and the planned 2022 Muon C/D trigger-trimmed NanoAOD production path.

## PCAS Schema Rule

The Pveto PCAS under `CustomNanoAOD/pocketcoffea_pveto/` targets DLS trigger-trimmed NanoAOD only. It uses central NanoAOD branches for standard object kinematics and IDs:

- `Muon_pt`, `Muon_eta`, `Muon_phi`, `Muon_charge`, `Muon_tightId`
- `Jet_pt`, `Jet_eta`, `Jet_phi`
- `Electron_eta`, `Electron_phi`
- `HLT_IsoMu24`

It keeps lowercase branch names only for custom DLS additions that are not central NanoAOD duplicates:

- `muon_isTrigMatched`
- `jet_isTightLepVeto`
- `metNoMu_pt`, `metNoMu_phi`
- required `trk_*` Pveto inputs

The old AI_disTk duplicate requirements such as `muon_pt`, `jet_pt`, `ele_eta`, and `ele_phi` are removed.

## Trigger Use During NanoAOD Production

The Muon skim customizer is selected with:

```bash
--customize disapptrks-muon-skim
```

That customizer inserts an `HLTHighLevel` filter into the NanoAOD path with:

```text
HLT_IsoMu24_v*
```

The output module is configured with `NANOAODoutput.SelectEvents`, so only events that pass the skim path are written to the output NanoAOD file.

For analysis after production, the PCAS reads the central event-level branch:

```text
HLT_IsoMu24
```

This is an event-level HLT bit. It is different from the old ntuplizer-style per-object trigger-matched boolean:

```text
muon_isTrigMatched
```

`muon_isTrigMatched` is produced by the DLS disappTrks custom table by matching `slimmedMuons` to `slimmedPatTrigger` trigger objects. For Run2022C/D Muon production, generated configs override the matching filter to:

```text
hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered0p08
```

This is needed for the pre-EE 2022 C/D IsoMu24 trigger-object matching used by the AI_disTk 2022 C/D custom NanoAOD configuration.

## CRAB Dry-Run Generation

Use MiniAOD inputs, not central NanoAOD:

```text
/Muon/Run2022C-22Sep2023-v1/MINIAOD
/Muon/Run2022D-22Sep2023-v1/MINIAOD
```

Generate configs inside a CMSSW environment:

```bash
cd /uscms/home/czheng/nobackup/CMSSW_15_0_10/src
cmsenv
cd DisplacedLeptonsSupplement

python3 CustomNanoAOD/scripts/make_nano_configs.py \
  CustomNanoAOD/scripts/datasets/Data_2022_Muon_CD_MINIAOD.txt \
  --output-dir CustomNanoAOD/generated_configs/disapptrks_muon_cd_2022 \
  --customize disapptrks-muon-skim \
  --out-lfn-dir-base /store/group/lpcdisapptrks/CollinTest
```

Before submission, check write access through CRAB:

```bash
crab checkwrite --site=T3_US_FNALLPC --lfn=/store/group/lpcdisapptrks/CollinTest
```

Dry-run inspection should verify:

- generated configs use `/MINIAOD` input datasets
- generated NanoAOD configs contain `HLTHighLevel`
- generated NanoAOD output modules contain `SelectEvents`
- CRAB configs use `T3_US_FNALLPC`
- CRAB configs use `/store/group/lpcdisapptrks/CollinTest`
- generated NanoAOD configs use `124X_dataRun3_v15`
- Run2022C/D generated NanoAOD configs use the pre-EE muon trigger-object matching filter ending in `Filtered0p08`

After dry-run inspection passes, submit with:

```bash
bash CustomNanoAOD/generated_configs/disapptrks_muon_cd_2022/submit_all.sh
```

In the 2026-06-17 dry run, the configs passed inspection but full C/D submission was not launched because the scale check suggested the output could be order TB:

- `/Muon/Run2022C-22Sep2023-v1/MINIAOD`: 138,329,693 events, 1,768 files, 6.29 TB input
- `/Muon/Run2022D-22Sep2023-v1/MINIAOD`: 75,440,027 events, 1,001 files, 3.43 TB input
- existing trigger-skim smoke output: 3.3 MB for 30 output events from 350 processed events

That extrapolation is too large to treat as a sub-200 GB validation test. Full submission should wait for explicit approval of that output scale, or use a bounded pilot CRAB config first.

Track runtime with:

```bash
crab status -d crab_projects/crab_Muon_Run2022C_disapptrks_muon_skim_customNanoAOD
crab status -d crab_projects/crab_Muon_Run2022D_disapptrks_muon_skim_customNanoAOD
```

## Relation To DisplacedLeptonsSupplement

The original upstream `DisplacedLeptonsSupplement` head did not contain the disappTrks NanoAOD tables or the Table 9 trigger skims. In the current `CollinKa/DisplacedLeptonsSupplement` repo, `disapptrks-muon-skim` is now part of the DLS code after the recent disappTrks NanoAOD merge. It follows the DLS style: Python customizers create the NanoAOD process changes, and C++ `FlatTable` producers write custom branches.

The new PCAS area is DLS-owned and assumes the output of that DLS trigger-trimmed NanoAOD workflow. It is derived from the AI_disTk Pveto PCAS logic, but it is intentionally not an AI_disTk lowercase-duplicate-schema compatibility layer.
