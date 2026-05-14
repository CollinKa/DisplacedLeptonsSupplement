import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing

options = VarParsing("analysis")
options.parseArguments()

process = cms.Process("MiniAODExtractor")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1000

process.maxEvents = cms.untracked.PSet(input = cms.untracked.int32(options.maxEvents))

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(options.inputFiles)
)

process.TFileService = cms.Service("TFileService",
    fileName = cms.string(options.outputFile)
)

process.extract = cms.EDAnalyzer("ExtractAnalyzer",
    src    = cms.InputTag("slimmedDisplacedMuons"),
    ptCut  = cms.double(15.0),
    variables = cms.PSet(
        DisplacedMuon_pt     = cms.string("pt()"),
        DisplacedMuon_eta    = cms.string("eta()"),
        DisplacedMuon_phi    = cms.string("phi()"),
        DisplacedMuon_dxy    = cms.string("dB('PV2D')"),
        DisplacedMuon_dxyErr = cms.string("edB('PV2D')"),
        DisplacedMuon_dz     = cms.string("dB('PVDZ')"),
        DisplacedMuon_dzErr  = cms.string("abs(edB('PVDZ'))"),
    )
)

process.p = cms.Path(process.extract)
