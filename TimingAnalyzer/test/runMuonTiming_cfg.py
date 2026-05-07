import FWCore.ParameterSet.Config as cms

process = cms.Process("SUPP")

process.load("FWCore.MessageLogger.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1000

process.load("Configuration.StandardSequences.GeometryRecoDB_cff")
process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
from Configuration.AlCa.GlobalTag import GlobalTag
process.GlobalTag = GlobalTag(process.GlobalTag, '106X_dataRun2_v35', '')

process.TFileService = cms.Service("TFileService",
    fileName = cms.string("supp_timing.root")
)

process.load("DisplacedLeptonsNanoSupplement.TimingAnalyzer.muonTimingAnalyzer_cfi")

process.p = cms.Path(process.muonTimingAnalyzer)

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(
        "/store/mc/RunIISummer20UL18MiniAODv2/ST_tW_top_5f_NoFullyHadronicDecays_TuneCP5_13TeV-powheg-pythia8/MINIAODSIM/106X_upgrade2018_realistic_v16_L1v1-v1/120000/28E98610-547D-1540-9100-FCF0ADA14FAF.root"
        # Replace with your MiniAOD file(s), e.g.:
        # "file:/path/to/MiniAOD.root"
        # "/store/data/Run2018A/DoubleMuon/MINIAOD/..."
    )
)

process.maxEvents = cms.untracked.PSet(input = cms.untracked.int32(-1))
