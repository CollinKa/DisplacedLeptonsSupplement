import FWCore.ParameterSet.Config as cms

process = cms.Process("DisplacedMuons")

process.load("FWCore.MessageService.MessageLogger_cfi")

process.MessageLogger.cerr.FwkReport.reportEvery = cms.untracked.int32(1000)
process.maxEvents = cms.untracked.PSet(input = cms.untracked.int32(-1))

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(
        "/store/mc/RunIII2024Summer24MiniAODv6/DYto2Mu-4Jets_Bin-MLL-50_TuneCP5_13p6TeV_madgraphMLM-pythia8/MINIAODSIM/150X_mcRun3_2024_realistic_v2-v3/110000/000c95c2-0866-40eb-8190-d02124662bf3.root",
        "/store/mc/RunIII2024Summer24MiniAODv6/DYto2Mu-4Jets_Bin-MLL-50_TuneCP5_13p6TeV_madgraphMLM-pythia8/MINIAODSIM/150X_mcRun3_2024_realistic_v2-v3/110000/004fa260-1e0a-4000-95fe-acf8feddabc6.root",
        "/store/mc/RunIII2024Summer24MiniAODv6/DYto2Mu-4Jets_Bin-MLL-50_TuneCP5_13p6TeV_madgraphMLM-pythia8/MINIAODSIM/150X_mcRun3_2024_realistic_v2-v3/110000/01ddae8b-6ca4-4240-8015-ebb91645c373.root"
    )
)

process.overlap = cms.EDAnalyzer("OverlapAnalyzer",
    promptSource = cms.InputTag("slimmedMuons"),
    displacedSource = cms.InputTag("slimmedDisplacedMuons"),
    min_dR = cms.double(0.1),
    min_dPtRelative = cms.double(0.1)
)

process.p = cms.Path(process.overlap)
