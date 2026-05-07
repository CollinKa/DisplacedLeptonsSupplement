import FWCore.ParameterSet.Config as cms

muonTimingAnalyzer = cms.EDAnalyzer("MuonTimingAnalyzer",
    # finalMuons: era-correct selection applied by muonSequence from muons_cff
    muonSrc     = cms.InputTag("finalMuons"),
    # slimmedElectrons: pt > 5 cut applied in C++ (matches NanoAOD finalElectrons)
    electronSrc = cms.InputTag("slimmedElectrons"),
)
