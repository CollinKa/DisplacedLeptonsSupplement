from CRABClient.UserUtilities import config

config = config()

config.General.requestName = 'DoubleMuon_Run2022C_customNanoAOD'
config.General.workArea = 'crab_projects'
config.General.transferOutputs = True
config.General.transferLogs = True

config.JobType.pluginName = 'Analysis'
config.JobType.psetName = 'DoubleMuon_Run2022C_NANO.py'
config.JobType.numCores = 1
config.JobType.outputFiles = ['nano.root']   # must match --fileout in cmsDriver

config.Data.inputDataset = '/DoubleMuon/Run2022C-22Sep2023-v1/MINIAOD'
config.Data.inputDBS = 'global'
config.Data.splitting = 'LumiBased'
config.Data.unitsPerJob = 50
config.Data.lumiMask = 'https://cms-service-dqmdc.web.cern.ch/CAF/certification/Collisions22/Cert_Collisions2022_355100_362760_Golden.json'
config.Data.publication = False

config.Data.outLFNDirBase = '/store/user/lnestor/customNanoAOD/Run2022/'
config.Data.outputDatasetTag = 'DoubleMuon_Run2022C_customNanoAOD'

config.Site.storageSite = 'T3_US_FNALLPC'
