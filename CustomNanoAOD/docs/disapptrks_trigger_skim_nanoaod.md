# DisappTrks Trigger Skim For Custom NanoAOD

This note explains how the disappearing-track custom NanoAOD configuration uses trigger requirements to reduce the number of events written to the output NanoAOD file.

## Where The Code Lives

Main implementation:

```text
CustomNanoAOD/python/disapp_trks_cff.py
```

Smoke-test example:

```text
CustomNanoAOD/test/disapptrks_run2022F_muon_skim_smoke_cfg.py
```

Config-generation hook:

```text
CustomNanoAOD/scripts/make_nano_configs.py
```

## Trigger Lists

The trigger path lists are defined in `disapp_trks_cff.py`.

MET/search skim:

```python
TABLE9_MET_HLT_PATHS = cms.vstring(
    "HLT_MET105_IsoTrk50_v*",
    "HLT_MET120_IsoTrk50_v*",
    "HLT_PFMET105_IsoTrk50_v*",
    "HLT_PFMET120_PFMHT120_IDTight_v*",
    "HLT_PFMET130_PFMHT130_IDTight_v*",
    "HLT_PFMET140_PFMHT140_IDTight_v*",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_v*",
    "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_v*",
    "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_v*",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_PFHT60_v*",
    "HLT_PFMETNoMu110_PFMHTNoMu110_IDTight_FilterHF_v*",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_FilterHF_v*",
    "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_FilterHF_v*",
    "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_FilterHF_v*",
    "HLT_PFMET120_PFMHT120_IDTight_PFHT60_v*",
)
```

Muon control skim:

```python
TABLE9_MUON_HLT_PATHS = cms.vstring(
    "HLT_IsoMu24_v*",
)
```

EGamma control skim:

```python
TABLE9_EGAMMA_HLT_PATHS = cms.vstring(
    "HLT_Ele32_WPTight_Gsf_v*",
)
```

The `v*` suffix is intentional. `cmsRun` filters on versioned HLT path names such as `HLT_IsoMu24_v15`, while the output NanoAOD event-level branch is normally the unversioned central NanoAOD branch such as `HLT_IsoMu24`.

## How The Skim Is Applied

The skim is applied by `AddDisappTrksTriggerSkim(process, hlt_paths, label)`.

That function does four things:

1. Creates an `HLTHighLevel` filter:

```python
cms.EDFilter(
    "HLTHighLevel",
    TriggerResultsTag=cms.InputTag("TriggerResults", "", "HLT"),
    HLTPaths=hlt_paths,
    eventSetupPathsKey=cms.string(""),
    andOr=cms.bool(True),
    throw=cms.bool(False),
)
```

Important settings:

- `TriggerResultsTag` reads the HLT trigger decision from MiniAOD.
- `HLTPaths` is the dataset-specific trigger list.
- `andOr=True` means the event passes if it fires at least one listed trigger.
- `throw=False` prevents a job failure if a configured path is absent in a particular run.

2. Finds the main NanoAOD path.

The helper first looks for:

```text
nanoAOD_step
nano_step
```

If neither exists, it searches for a path with `nano` in the name.

3. Inserts the trigger filter at the start of the NanoAOD path.

Conceptually, the path becomes:

```text
HLTHighLevel trigger filter -> NanoAOD producers
```

For the muon skim smoke test, this produced:

```text
disappTrksMuonTriggerFilter -> nanoSequence
```

4. Restricts the NanoAOD output module with `SelectEvents`.

This is the key file-size step:

```python
process.NANOAODoutput.SelectEvents = cms.untracked.PSet(
    SelectEvents=cms.vstring(path_name)
)
```

Only events that pass the skimmed NanoAOD path are written to the output file. Events that fail the trigger filter are processed enough to make the path decision, but are not saved in the NanoAOD output.

## Dataset-Specific Wrappers

The user-facing wrappers are:

```python
def AddDisappTrksMETTriggerSkim(process):
    return AddDisappTrksTriggerSkim(process, TABLE9_MET_HLT_PATHS, "MET")

def AddDisappTrksMuonTriggerSkim(process):
    return AddDisappTrksTriggerSkim(process, TABLE9_MUON_HLT_PATHS, "Muon")

def AddDisappTrksEGammaTriggerSkim(process):
    return AddDisappTrksTriggerSkim(process, TABLE9_EGAMMA_HLT_PATHS, "EGamma")
```

The combined DLS-style customizers are exposed through:

```text
CustomNanoAOD/python/custom_displaced_leptons_cff.py
```

with names:

```text
PrepDisplacedLeptonsDisappTrksNanoAOD_METSkim
PrepDisplacedLeptonsDisappTrksNanoAOD_MuonSkim
PrepDisplacedLeptonsDisappTrksNanoAOD_EGammaSkim
```

## Smoke-Test Example

The current small test config uses the muon trigger skim:

```text
CustomNanoAOD/test/disapptrks_run2022F_muon_skim_smoke_cfg.py
```

The important lines are:

```python
process = AddDisappTrksNanoTables(process)
process.nanoAOD_step = cms.Path(process.nanoSequence)
process.NANOAODoutput = cms.OutputModule(...)
process.end = cms.EndPath(process.NANOAODoutput)
process = AddDisappTrksMuonTriggerSkim(process)
process.schedule = cms.Schedule(process.nanoAOD_step, process.end)
```

The order matters:

- The NanoAOD path and output module must exist.
- Then `AddDisappTrksMuonTriggerSkim` can insert the HLT filter and attach `SelectEvents` to the output module.

## Verified Behavior

The successful Run2022F muon-skim smoke test used:

```text
cmsRun CustomNanoAOD/test/disapptrks_run2022F_muon_skim_smoke_cfg.py \
  maxEvents=350 \
  outputFile=/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/test_outputs/disapptrks_run2022F_muon_skim_max350_dlsfixed2.root
```

The actual output file was:

```text
/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/DisplacedLeptonsSupplement/CustomNanoAOD/test_outputs/disapptrks_run2022F_muon_skim_max350_dlsfixed2_numEvent350.root
```

Observed result:

```text
Input events processed: 350
Events passing HLT_IsoMu24_v*: 30
Events written to NanoAOD: 30
Output size: 3,445,086 bytes
```

The output file contains the central event-level trigger branch:

```text
HLT_IsoMu24: Bool_t
```

That branch is for later analysis checks. The skim decision during `cmsRun` uses the versioned HLT pattern from `TriggerResults`.

## Important Distinction

There are two trigger concepts in this workflow:

1. Event-level skim at NanoAOD production time.

This is the `HLTHighLevel` filter plus `NANOAODoutput.SelectEvents`. It reduces file size by not writing trigger-failing events.

2. Per-object trigger matching saved in custom branches.

These branches are analysis helper variables:

```text
muon_isTrigMatched
ele_isTrigMatched
```

They do not decide whether the event is written. They record whether a reconstructed muon or electron is geometrically matched to a configured trigger object/filter after the event has already passed the event-level skim.

## Production Guidance

Use skimmed production for smaller files:

```text
--customize disapptrks-met-skim
--customize disapptrks-muon-skim
--customize disapptrks-egamma-skim
```

Use unskimmed validation production when trigger-efficiency denominators are needed:

```text
--customize disapptrks
```

Do not measure trigger efficiency using a file that has already been skimmed by the same trigger. The denominator would already have trigger-failing events removed.

## Relation To DisplacedLeptonsSupplement HEAD

This disappearing-track trigger skim is implemented as an addition to the existing `DisplacedLeptonsSupplement` customized NanoAOD style, not as a separate production framework.

At `DisplacedLeptonsSupplement` HEAD, customized NanoAOD production is organized around:

- small Python customization functions under `CustomNanoAOD/python/`
- C++ CMSSW producers under `CustomNanoAOD/plugins/`
- config-generation helpers under `CustomNanoAOD/scripts/`

The disappearing-track merge follows that same structure:

- `custom_displaced_leptons_cff.py` remains the top-level DLS customization entry point.
- `disapp_trks_cff.py` adds the disappearing-track NanoAOD tables and optional trigger skims.
- `DisappTrksNanoTables.cc` writes the custom `FlatTable` branches.
- `make_nano_configs.py` exposes DLS-style options such as `--customize disapptrks-muon-skim`.

The combined customizer is designed to call the existing DLS displaced-lepton preparation first, then add the disappearing-track tables and optional trigger filtering. In other words, for customized NanoAOD production this is an extension of the familiar DLS workflow:

```text
DisplacedLeptonsSupplement HEAD customized NanoAOD
  + disappTrks FlatTable branches
  + optional Table 9 trigger skim
  = DLS-style disappearing-track customized NanoAOD
```

The trigger skim itself is therefore not a replacement for the DLS customized NanoAOD machinery. It is a small DLS-style customization layer that reduces the output event count before `NANOAODoutput` writes the file.
