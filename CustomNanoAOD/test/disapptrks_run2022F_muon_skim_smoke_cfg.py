import FWCore.ParameterSet.Config as cms
from Configuration.AlCa.GlobalTag import GlobalTag
from Configuration.Eras.Era_Run3_cff import Run3
from FWCore.ParameterSet.VarParsing import VarParsing

from DisplacedLeptonsSupplement.CustomNanoAOD.disapp_trks_cff import (
    AddDisappTrksMuonTriggerSkim,
    AddDisappTrksNanoTables,
)


options = VarParsing("analysis")
options.outputFile = (
    "/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/"
    "DisplacedLeptonsSupplement/CustomNanoAOD/test_outputs/"
    "disapptrks_run2022F_muon_skim_10.root"
)
options.maxEvents = 10
options.inputFiles = [
    "file:/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/AI_disTk/local_samples/run2022F/miniaod.root"
]
options.parseArguments()

process = cms.Process("NANO", Run3)
process.options = cms.untracked.PSet(wantSummary=cms.untracked.bool(True))

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 10

process.load("Configuration.StandardSequences.Services_cff")
process.load("Configuration.StandardSequences.GeometryRecoDB_cff")
process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
process.GlobalTag = GlobalTag(process.GlobalTag, "124X_dataRun3_PromptAnalysis_v2", "")

process.source = cms.Source("PoolSource", fileNames=cms.untracked.vstring(options.inputFiles))
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(options.maxEvents))

process.load("PhysicsTools.NanoAOD.nano_cff")

# Run2022F PromptReco MiniAOD compatibility guards copied from the current
# AI_disTk validation config. These remove standard NanoAOD pieces whose inputs
# are absent in this local MiniAOD test file, while keeping the disTk custom
# table under test.
if hasattr(process, "nanoSequence") and hasattr(process, "lhcInfoTable"):
    process.nanoSequence.remove(process.lhcInfoTable)

if hasattr(process, "jetPuppiTable") and hasattr(process.jetPuppiTable.variables, "puIdDisc"):
    del process.jetPuppiTable.variables.puIdDisc

if hasattr(process, "electronTask"):
    for _module in ("bitmapVIDForEle", "bitmapVIDForEleFall17V2", "bitmapVIDForEleHEEP"):
        if hasattr(process, _module):
            process.electronTask.remove(getattr(process, _module))
if hasattr(process, "slimmedElectronsWithUserData"):
    for _name in (
        "mvaIso_Fall17V2",
        "mvaNoIso_Fall17V2",
        "mvaIso",
        "mvaNoIso",
        "mvaHZZIso",
    ):
        if hasattr(process.slimmedElectronsWithUserData.userFloats, _name):
            delattr(process.slimmedElectronsWithUserData.userFloats, _name)
    for _name in (
        "mvaIso_Fall17V2_WP90",
        "mvaIso_Fall17V2_WP80",
        "mvaIso_Fall17V2_WPL",
        "mvaIso_WP90",
        "mvaIso_WP80",
        "mvaNoIso_Fall17V2_WP90",
        "mvaNoIso_Fall17V2_WP80",
        "mvaNoIso_Fall17V2_WPL",
        "mvaNoIso_WP90",
        "mvaNoIso_WP80",
        "mvaIso_WPHZZ",
        "cutBasedID_veto",
        "cutBasedID_loose",
        "cutBasedID_medium",
        "cutBasedID_tight",
        "cutBasedID_Fall17V2_veto",
        "cutBasedID_Fall17V2_loose",
        "cutBasedID_Fall17V2_medium",
        "cutBasedID_Fall17V2_tight",
        "cutBasedID_HEEP",
    ):
        if hasattr(process.slimmedElectronsWithUserData.userIntFromBools, _name):
            delattr(process.slimmedElectronsWithUserData.userIntFromBools, _name)
    for _name in ("VIDNestedWPBitmap", "VIDNestedWPBitmap_Fall17V2", "VIDNestedWPBitmapHEEP"):
        if hasattr(process.slimmedElectronsWithUserData.userInts, _name):
            delattr(process.slimmedElectronsWithUserData.userInts, _name)
if hasattr(process, "electronTable"):
    for _name in (
        "cutBased",
        "cutBased_Fall17V2",
        "cutBased_HEEP",
        "mvaIso",
        "mvaIso_WP80",
        "mvaIso_WP90",
        "mvaNoIso",
        "mvaNoIso_WP80",
        "mvaNoIso_WP90",
        "mvaHZZIso",
        "mvaIso_WPHZZ",
        "promptMVA",
        "vidNestedWPBitmap",
        "vidNestedWPBitmapHEEP",
    ):
        if hasattr(process.electronTable.variables, _name):
            delattr(process.electronTable.variables, _name)
if hasattr(process, "nanoTableTaskCommon") and hasattr(process, "electronTablesTask"):
    process.nanoTableTaskCommon.remove(process.electronTablesTask)
if hasattr(process, "linkedObjects") and hasattr(process.linkedObjects, "electrons"):
    process.linkedObjects.electrons = cms.InputTag("finalElectrons")

if hasattr(process, "nanoTableTaskCommon"):
    for _task_name in ("boostedTauTablesTask", "boostedTauTask"):
        if hasattr(process, _task_name):
            process.nanoTableTaskCommon.remove(getattr(process, _task_name))
if hasattr(process, "linkedObjects") and hasattr(process.linkedObjects, "boostedTaus"):
    process.linkedObjects.boostedTaus = cms.InputTag("slimmedTaus")

if hasattr(process, "nanoTableTaskCommon"):
    for _task_name in ("photonTablesTask", "photonTask"):
        if hasattr(process, _task_name):
            process.nanoTableTaskCommon.remove(getattr(process, _task_name))
if hasattr(process, "linkedObjects") and hasattr(process.linkedObjects, "photons"):
    process.linkedObjects.photons = cms.InputTag("slimmedPhotons")

if hasattr(process, "nanoTableTaskCommon"):
    for _task_name in ("tauTablesTask", "tauTask"):
        if hasattr(process, _task_name):
            process.nanoTableTaskCommon.remove(getattr(process, _task_name))
if hasattr(process, "linkedObjects") and hasattr(process.linkedObjects, "taus"):
    process.linkedObjects.taus = cms.InputTag("slimmedTaus")

process = AddDisappTrksNanoTables(process)

process.nanoAOD_step = cms.Path(process.nanoSequence)

process.NANOAODoutput = cms.OutputModule(
    "NanoAODOutputModule",
    fileName=cms.untracked.string(options.outputFile),
    outputCommands=process.NANOAODEventContent.outputCommands,
    compressionAlgorithm=cms.untracked.string("LZMA"),
    compressionLevel=cms.untracked.int32(9),
)
process.end = cms.EndPath(process.NANOAODoutput)

process = AddDisappTrksMuonTriggerSkim(process)

process.schedule = cms.Schedule(process.nanoAOD_step, process.end)
