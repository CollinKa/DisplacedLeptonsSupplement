import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing

options = VarParsing("analysis")
options.register("globalTag", "94X_dataRun2_v11",
    VarParsing.multiplicity.singleton, VarParsing.varType.string,
    "Global tag — must match the dataset era")
options.parseArguments()

process = cms.Process("POCAVerification")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1000

process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
from Configuration.AlCa.GlobalTag import GlobalTag
process.GlobalTag = GlobalTag(process.GlobalTag, options.globalTag, "")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(options.maxEvents))

process.source = cms.Source("PoolSource",
    fileNames=cms.untracked.vstring(options.inputFiles)
)

process.TFileService = cms.Service("TFileService",
    fileName=cms.string(options.outputFile)
)

process.leptonPoca = cms.EDAnalyzer("LeptonPocaAnalyzer",
    muons     = cms.InputTag("slimmedMuons"),
    electrons = cms.InputTag("slimmedElectrons"),
    ptCut     = cms.double(5.0),
)

process.p = cms.Path(process.leptonPoca)
