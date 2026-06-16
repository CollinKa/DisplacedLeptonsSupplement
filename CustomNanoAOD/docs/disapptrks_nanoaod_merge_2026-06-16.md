# Disappearing-Track NanoAOD Merge Trace

Date: 2026-06-16

## Source And Target

- Requested source repository: `git@github.com:CollinKa/DisplacedLeptonsSupplement.git`
- Staged checkout used here: `/private/tmp/CollinKa_DisplacedLeptonsSupplement`
- Requested LPC target: `/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement`
- The implementation was first staged in `/private/tmp`, then copied to the requested LPC target through `ssh -Y czheng@cmslpc-el9.fnal.gov`.
- No files were deleted.
- No ROOT outputs or large files were produced.

## Implemented Changes

- Added `CustomNanoAOD/plugins/DisappTrksNanoTables.cc` from the current AI_disTk `NanoAOD/plugins/DisappTrksNanoTables.cc`.
- Updated `CustomNanoAOD/plugins/BuildFile.xml` with the CMSSW dependencies needed by the disTk table producer.
- Added `CustomNanoAOD/python/disapp_trks_cff.py` with:
  - unskimmed disTk table setup
  - Table 9 MET trigger skim
  - Table 9 Muon trigger skim
  - Table 9 EGamma trigger skim
- Extended `CustomNanoAOD/python/custom_displaced_leptons_cff.py` with combined customizers:
  - `PrepDisplacedLeptonsDisappTrksNanoAOD`
  - `PrepDisplacedLeptonsDisappTrksNanoAOD_METSkim`
  - `PrepDisplacedLeptonsDisappTrksNanoAOD_MuonSkim`
  - `PrepDisplacedLeptonsDisappTrksNanoAOD_EGammaSkim`
- Extended `CustomNanoAOD/scripts/make_nano_configs.py` with:
  - `--customize displaced-leptons`
  - `--customize disapptrks`
  - `--customize disapptrks-met-skim`
  - `--customize disapptrks-muon-skim`
  - `--customize disapptrks-egamma-skim`
  - `--out-lfn-dir-base`, which should be set to `/store/group/lpcdisapptrks/CollinTest` for larger disTk validation tests.

## Trigger Skim Policy

- MET/search production uses the OR of the Table 9 MET triggers.
- Muon control production uses `HLT_IsoMu24`.
- EGamma control production uses `HLT_Ele32_WPTight_Gsf`.
- The HLT filter uses versioned path patterns such as `HLT_IsoMu24_v*`.
- The output module is configured with `SelectEvents` so trigger-fail events are not saved in skim mode.
- The filter is prepended to the main NanoAOD path when that path is found.

## Branch Scope

- The first implementation keeps all current custom disTk `trk_*` and `vtx_*` branches from AI_disTk.
- It keeps only the missing object extras needed by the current analysis:
  - `muon_isTrigMatched`
  - `muon_pfRelIso04_dBeta`
  - `ele_isTrigMatched`
  - `tau_isTight`
  - `tau_decayModeFindingNewDMs`
  - `jet_isTightLepVeto`
  - event-level `metNoMu_pt` and `metNoMu_phi`
- It does not keep duplicate lowercase kinematic/rho outputs such as `muon_pt`, `ele_pt`, `tau_pt`, `jet_pt`, `met_pt`, or `rho_all`, because central NanoAOD already provides those data in standard branches.
- Central NanoAOD branches are not duplicated with capitalized names.
- `trk_crossedEcalStatus` and `trk_crossedHcalStatus` remain skipped because nested vectors do not map directly to scalar NanoAOD `FlatTable` columns.

## Validation Performed

- Python syntax check passed for:
  - `CustomNanoAOD/scripts/make_nano_configs.py`
  - `CustomNanoAOD/python/custom_displaced_leptons_cff.py`
  - `CustomNanoAOD/python/disapp_trks_cff.py`
- LPC targeted package build passed:
  - `scram b -j 8 DisplacedLeptonsSupplement/CustomNanoAOD`
- LPC customizer import check passed:
  - MET trigger paths: 15
  - Muon trigger paths: 1
  - EGamma trigger paths: 1
- Renamed the DLS producer plugin classes to avoid loading the old AI_disTk `DisappTrkTableProducer` plugin from the same CMSSW area:
  - `DLSDisappTrkTableProducer`
  - `DLSDisappMuonTableProducer`
  - `DLSDisappObjectTablesProducer`
  - `DLSDisappMetNoMuTableProducer`
- Refreshed the CMSSW plugin cache with `edmPluginRefresh`; `edmPluginHelp -p DLSDisappTrkTableProducer` then resolved to `pluginDisplacedLeptonsSupplementCustomNanoAODAuto.so`.
- A first DLS-fixed smoke attempt failed because `Muon`/`Electron`/`Tau`/`Jet` extension tables were encountered before the corresponding central main tables by `NanoAODOutputModule`.
- Fixed that by saving only missing object extras in lowercase DLS compatibility tables instead of central extension tables.
- Final 350-event Run2022F Muon-skim smoke test passed:
  - input MiniAOD: `/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/AI_disTk/local_samples/run2022F/miniaod.root`
  - output NanoAOD: `/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/test_outputs/disapptrks_run2022F_muon_skim_max350_dlsfixed2_numEvent350.root`
  - processed events: 350
  - trigger-passing saved events: 30
- Branch-policy validation passed:
  - result JSON: `/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/validation/results/branch_policy_disapptrks_run2022F_muon_skim_max350_dlsfixed2.json`
  - disallowed duplicate count: 0
  - expected custom additions missing: 0
  - `trk_*` branches: 118
  - `vtx_*` branches: 12
- First-10 NanoAOD events were matched back to MiniAOD by `(run, lumi, event)` and compared with ROOT/FWLite:
  - result JSON: `/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/validation/results/compare_miniaod_first10_disapptrks_run2022F_muon_skim_max350_dlsfixed2.json`
  - matched events: 10
  - checked values: 370
  - failures: 0

## Completed LPC Setup

- Cloned `https://github.com/CollinKa/DisplacedLeptonsSupplement.git` into:
  - `/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement`
- Applied the disTk custom NanoAOD changes in that checkout.
- Built the target CMSSW package successfully.

## Remaining LPC Follow-Up

Generate an unskimmed disTk validation config from `/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement`:

```bash
python3 CustomNanoAOD/scripts/make_nano_configs.py DATASETS.txt \
  --output-dir configs_disapptrks_unskimmed \
  --customize disapptrks
```

Generate a MET-skimmed config:

```bash
python3 CustomNanoAOD/scripts/make_nano_configs.py DATASETS.txt \
  --output-dir configs_disapptrks_met_skim \
  --customize disapptrks-met-skim \
  --out-lfn-dir-base /store/group/lpcdisapptrks/CollinTest
```

For larger tests, estimate output size before launching CRAB. Keep total output below 200 GB unless explicitly approved.
