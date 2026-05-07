import FWCore.ParameterSet.Config as cms
from Configuration.Eras.Era_Run2_2018_cff import Run2_2018
from Configuration.Eras.Modifier_run2_nanoAOD_106Xv1_cff import run2_nanoAOD_106Xv1

# Era Run2_2018 + run2_nanoAOD_106Xv1 causes muons_cff to apply the NanoAODv9
# muon selection: pt > 3 && (CutBasedIdLoose || SoftCutBasedId || SoftMvaId || ...)
# instead of the default pt > 15 || (pt > 3 && IDs). This must match the era used
# during NanoAODv9 production for indices to be correct.
process = cms.Process("SUPP", Run2_2018, run2_nanoAOD_106Xv1)

process.load("FWCore.MessageLogger.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1000

process.load("Configuration.StandardSequences.GeometryRecoDB_cff")
process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
from Configuration.AlCa.GlobalTag import GlobalTag
# Use the global tag matching your dataset:
#   2016 data UL: 106X_dataRun2_v37
#   2017 data UL: 106X_dataRun2_v37
#   2018 data UL: 106X_dataRun2_v35
#   MC UL:        106X_mc2017_realistic_v9  (or similar — check your dataset)
process.GlobalTag = GlobalTag(process.GlobalTag, '106X_dataRun2_v35', '')

# Loads muonSequence (slimmedMuonsUpdated + isoForMu + ptRatioRelForMu +
# slimmedMuonsWithUserData + finalMuons + finalLooseMuons) with era modifiers applied.
process.load("PhysicsTools.NanoAOD.muons_cff")

process.TFileService = cms.Service("TFileService",
    fileName = cms.string("supp_timing.root")
)

process.load("NanoSupplement.TimingAnalyzer.muonTimingAnalyzer_cfi")

# muonSequence must run before the analyzer so finalMuons is available.
# Electrons are read directly from slimmedElectrons (no sequence needed).
process.p = cms.Path(
    process.muonSequence *
    process.muonTimingAnalyzer
)

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(
        # Replace with your MiniAOD file(s), e.g.:
        # "file:/path/to/MiniAOD.root"
        # "/store/data/Run2018A/DoubleMuon/MINIAOD/..."
    )
)

process.maxEvents = cms.untracked.PSet(input = cms.untracked.int32(-1))
