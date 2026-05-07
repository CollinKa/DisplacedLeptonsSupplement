import FWCore.ParameterSet.Config as cms

muonTimingAnalyzer = cms.EDAnalyzer("MuonTimingAnalyzer",
    # NanoAODv9 selection applied in C++: pt > 3 && (standard IDs)
    muonSrc     = cms.InputTag("slimmedMuons"),
    # NanoAODv9 selection applied in C++: pt > 5
    electronSrc = cms.InputTag("slimmedElectrons"),
)
