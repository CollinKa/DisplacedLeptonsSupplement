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

## Compatibility Notes

`ApplyDisappTrksRun3MiniAODCompatibility` currently removes `lhcInfoTable` from `nanoSequence` and `nanoSequenceOnlyData`. This was done because the 2022 C/D MiniAOD pilot failed when `lhcInfoTable` tried to read `LHCInfoPerLSRcd`, which was not available in that running context. This is a production-compatibility workaround, not a physics requirement of the disappearing-track analysis. If a future CMSSW/input setup provides the needed record, or if luminosity-section LHC information is needed, this table should be re-enabled through an explicit option in the compatibility customizer.

The same compatibility customizer also narrows the standard `jetTable` to `Jet_pt`, `Jet_eta`, and `Jet_phi` and removes standard b/c regression modules that needed unavailable MiniAOD user floats. It does not apply the old `DisappTrks_v2` explicit JEC machinery.

For the current DLS trigger-trimmed NanoAOD production, jet kinematics follow the standard NanoAOD/global-tag path from the generated CMSSW config:

```text
124X_dataRun3_v15
```

I did not port the old `DisappTrks_v2` JEC path that passed explicit files like:

```text
DisappTrks_v2/data/JecConfigAK4.json
DisappTrks_v2/data/jer_smear.json.gz
```

and then ran producers such as:

```text
jecAppliedJetProducer
jecAppliedMetProducer
```

For 2022 pre-EE data, that old config points at payload names such as:

```text
Summer22_22Sep2023_V4_DATA_L1FastJet_AK4PFPuppi
Summer22_22Sep2023_V4_DATA_L2Relative_AK4PFPuppi
Summer22_22Sep2023_V4_DATA_L2L3Residual_AK4PFPuppi
```

So the current submitted DLS C/D jobs do not use the explicit AI_disTk/DisappTrks_v2 JEC versioning. They use the DLS/cmsDriver/global-tag NanoAOD behavior.

After dry-run inspection passes, submit with:

```bash
cd /uscms/home/czheng/nobackup/CMSSW_15_0_10/src
cmsenv
cd DisplacedLeptonsSupplement/CustomNanoAOD/generated_configs/disapptrks_muon_cd_2022
bash submit_all.sh
```

The generated `submit_all.sh` intentionally changes into its own directory before running `crab submit`, because the CRAB configs use basename `psetName` values.

## 2026-06-17 Pilot Measurement And Submission

After explicit approval to do a small pilot output-size measurement and submit the Era C/D production jobs, I ran 1000-input-event local pilots from one MiniAOD file per era.

Run2022C pilot:

- input: `/store/data/Run2022C/Muon/MINIAOD/22Sep2023-v1/50000/c5509051-eba0-404d-a18d-40f60e42b418.root`
- output: `CustomNanoAOD/test_outputs/pilot_20260617_muon_cd/pilot_Run2022C_disapptrks_muon_skim_fixed6_1000.root`
- processed input events: 1000
- output events after `HLT_IsoMu24_v*` skim: 539
- output size: 5,155,436 bytes, shown by `ls` as 5.0M
- runtime: 99.82 seconds real time

Run2022D pilot:

- input: `/store/data/Run2022D/Muon/MINIAOD/22Sep2023-v1/2520000/77b001b7-7d84-4544-a932-2960748112d1.root`
- output: `CustomNanoAOD/test_outputs/pilot_20260617_muon_cd/pilot_Run2022D_disapptrks_muon_skim_fixed6_1000.root`
- processed input events: 1000
- output events after `HLT_IsoMu24_v*` skim: 508
- output size: 4,999,439 bytes, shown by `ls` as 4.8M
- runtime: 218.49 seconds real time

Both pilot files contain the required DLS-trimmed NanoAOD branches:

```text
Electron_eta
Electron_phi
Muon_pt
Jet_pt
Jet_eta
Jet_phi
trk_pt
metNoMu_pt
muon_isTrigMatched
jet_isTightLepVeto
HLT_IsoMu24
```

The central MiniAOD input sizes are not a local or group-storage requirement. CRAB reads the MiniAOD from CMS data storage. The group storage cost is the produced NanoAOD output.

Using the 1000-event pilots as a first-file estimate:

- `/Muon/Run2022C-22Sep2023-v1/MINIAOD`: 138,329,693 events, 1,768 files, 6.29 TB input
- `/Muon/Run2022D-22Sep2023-v1/MINIAOD`: 75,440,027 events, 1,001 files, 3.43 TB input
- estimated Run2022C output: about 713 GB decimal
- estimated Run2022D output: about 377 GB decimal
- estimated combined output: about 1.09 TB decimal

This is a pilot estimate, not a final accounting. The output can vary across files because event content and trigger acceptance vary.

The full CRAB tasks were submitted from:

```bash
cd /uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/generated_configs/disapptrks_muon_cd_2022
crab submit crab_Muon_Run2022C_disapptrks_muon_skim.py
crab submit crab_Muon_Run2022D_disapptrks_muon_skim.py
```

Run2022C task:

```text
260617_050505:hazheng_crab_Muon_Run2022C_disapptrks_muon_skim_customNanoAOD
```

Project directory:

```text
/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/generated_configs/disapptrks_muon_cd_2022/crab_projects/crab_Muon_Run2022C_disapptrks_muon_skim_customNanoAOD
```

Immediate status after submission:

```text
SUBMITTED
```

Run2022D task:

```text
260617_050550:hazheng_crab_Muon_Run2022D_disapptrks_muon_skim_customNanoAOD
```

Project directory:

```text
/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/generated_configs/disapptrks_muon_cd_2022/crab_projects/crab_Muon_Run2022D_disapptrks_muon_skim_customNanoAOD
```

Immediate status after submission:

```text
QUEUED on command SUBMIT
```

There was one failed submit attempt from the repo root before the `submit_all.sh` path handling was fixed. That attempt failed because CRAB could not find the basename `psetName` from the wrong working directory. It left a partial local work area at:

```text
/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/crab_projects/crab_Muon_Run2022C_disapptrks_muon_skim_customNanoAOD
```

`crab status` reported that this directory has no `.requestcache`, so it is not a registered CRAB task. It was not deleted.

Track runtime with:

```bash
cd /uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/generated_configs/disapptrks_muon_cd_2022
crab status -d crab_projects/crab_Muon_Run2022C_disapptrks_muon_skim_customNanoAOD
crab status -d crab_projects/crab_Muon_Run2022D_disapptrks_muon_skim_customNanoAOD
```

Final status snapshot from this pass:

- Run2022C: CRAB server `SUBMITTED`, scheduler `SUBMITTED`, 252/256 jobs idle and 4/256 running.
- Run2022D: CRAB server `SUBMITTED`, scheduler `SUBMITTED`, 17/149 jobs running and 132/149 unsubmitted.
- Both tasks request 3000 MB; CRAB warns that only 2500 MB is guaranteed at many sites, so the first failures or holds should be checked for memory pressure.

## Relation To DisplacedLeptonsSupplement

The original upstream `DisplacedLeptonsSupplement` head did not contain the disappTrks NanoAOD tables or the Table 9 trigger skims. In the current `CollinKa/DisplacedLeptonsSupplement` repo, `disapptrks-muon-skim` is now part of the DLS code after the recent disappTrks NanoAOD merge. It follows the DLS style: Python customizers create the NanoAOD process changes, and C++ `FlatTable` producers write custom branches.

The new PCAS area is DLS-owned and assumes the output of that DLS trigger-trimmed NanoAOD workflow. It is derived from the AI_disTk Pveto PCAS logic, but it is intentionally not an AI_disTk lowercase-duplicate-schema compatibility layer.
