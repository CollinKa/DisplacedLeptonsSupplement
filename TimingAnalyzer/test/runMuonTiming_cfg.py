import FWCore.ParameterSet.Config as cms

process = cms.Process("SUPP")

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

process.TFileService = cms.Service("TFileService",
    fileName = cms.string("supp_timing.root")
)

process.load("DisplacedLeptonsNanoSupplement.TimingAnalyzer.muonTimingAnalyzer_cfi")

process.p = cms.Path(process.muonTimingAnalyzer)

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(
        # Replace with your MiniAOD file(s), e.g.:
        # "file:/path/to/MiniAOD.root"
        # "/store/data/Run2018A/DoubleMuon/MINIAOD/..."
    )
)

process.maxEvents = cms.untracked.PSet(input = cms.untracked.int32(-1))
