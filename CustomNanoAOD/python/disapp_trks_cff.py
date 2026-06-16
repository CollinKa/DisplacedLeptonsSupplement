import FWCore.ParameterSet.Config as cms

CUSTOM_DISAPP_TRKS_NANO_VERSION = 1

TABLE9_MET_HLT_PATHS = cms.vstring(
    "HLT_MET105_IsoTrk50_v*",
    "HLT_MET120_IsoTrk50_v*",
    "HLT_PFMET105_IsoTrk50_v*",
    "HLT_PFMET120_PFMHT120_IDTight_v*",
    "HLT_PFMET130_PFMHT130_IDTight_v*",
    "HLT_PFMET140_PFMHT140_IDTight_v*",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_v*",
    "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_v*",
    "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_v*",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_PFHT60_v*",
    "HLT_PFMETNoMu110_PFMHTNoMu110_IDTight_FilterHF_v*",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_FilterHF_v*",
    "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_FilterHF_v*",
    "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_FilterHF_v*",
    "HLT_PFMET120_PFMHT120_IDTight_PFHT60_v*",
)

TABLE9_MUON_HLT_PATHS = cms.vstring(
    "HLT_IsoMu24_v*",
)

TABLE9_EGAMMA_HLT_PATHS = cms.vstring(
    "HLT_Ele32_WPTight_Gsf_v*",
)


def _set_metadata(process, key, value):
    if hasattr(process, "nanoMetadata"):
        setattr(process.nanoMetadata.strings, key, cms.string(str(value)))
    return process


def _add_to_nano_task_or_schedule(process, module_name, path_name):
    module = getattr(process, module_name)
    if hasattr(process, "nanoTableTaskCommon"):
        process.nanoTableTaskCommon.add(module)
        return process
    if hasattr(process, "nanoTableTask"):
        process.nanoTableTask.add(module)
        return process

    setattr(process, path_name, cms.Path(module))
    if hasattr(process, "schedule"):
        process.schedule.extend([getattr(process, path_name)])
    return process


def _select_output_events(process, path_name):
    select_events = cms.untracked.PSet(SelectEvents=cms.vstring(path_name))
    selected = False
    for output_name in ("NANOAODoutput", "NANOAODSIMoutput"):
        if hasattr(process, output_name):
            getattr(process, output_name).SelectEvents = select_events
            selected = True

    if selected:
        return process

    if hasattr(process, "outputModules_"):
        for output_module in process.outputModules_().values():
            output_module.SelectEvents = select_events
    return process


def _find_main_nanoaod_path(process):
    for path_name in ("nanoAOD_step", "nano_step"):
        if hasattr(process, path_name):
            return path_name

    if hasattr(process, "paths_"):
        for path_name in process.paths_():
            if "nano" in path_name.lower():
                return path_name
    return None


def AddDisappTrksNanoTables(process):
    process.disappTrkTable = cms.EDProducer(
        "DLSDisappTrkTableProducer",
        tracks=cms.InputTag("isolatedTracks"),
        rhoAll=cms.InputTag("fixedGridRhoFastjetAll"),
        rhoAllCalo=cms.InputTag("fixedGridRhoFastjetAllCalo"),
        rhoCentralCalo=cms.InputTag("fixedGridRhoFastjetCentralCalo"),
        muons=cms.InputTag("slimmedMuons"),
        vertices=cms.InputTag("offlineSlimmedPrimaryVertices"),
        triggerObjects=cms.InputTag("slimmedPatTrigger"),
        triggerResults=cms.InputTag("TriggerResults", "", "HLT"),
        electrons=cms.InputTag("slimmedElectrons"),
        taus=cms.InputTag("slimmedTaus"),
        jets=cms.InputTag("slimmedJets"),
        met=cms.InputTag("slimmedMETs"),
        triggerFilterName=cms.string("hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered"),
        electronTriggerFilterName=cms.string("hltEle32WPTightGsfTrackIsoFilter"),
        triggerMatchingDR=cms.double(0.3),
        electronIdLabel=cms.string("cutBasedElectronID-RunIIIWinter22-V1-tight"),
        tauVsJetLabel=cms.string(""),
        tauVsEleLabel=cms.string("byVVVLooseDeepTau2018v2p5VSe"),
        tauVsMuLabel=cms.string("byVLooseDeepTau2018v2p5VSmu"),
        maskedEcalChannelStatusThreshold=cms.int32(3),
    )
    process = _add_to_nano_task_or_schedule(process, "disappTrkTable", "disappTrksNano_step")
    process = _set_metadata(process, "customDisappTrksNanoVersion", CUSTOM_DISAPP_TRKS_NANO_VERSION)
    process = _set_metadata(process, "customDisappTrksTriggerSkim", "none")
    return process


def AddDisappTrksTriggerSkim(process, hlt_paths, label):
    filter_name = "disappTrks{}TriggerFilter".format(label)
    setattr(
        process,
        filter_name,
        cms.EDFilter(
            "HLTHighLevel",
            TriggerResultsTag=cms.InputTag("TriggerResults", "", "HLT"),
            HLTPaths=hlt_paths,
            eventSetupPathsKey=cms.string(""),
            andOr=cms.bool(True),
            throw=cms.bool(False),
        ),
    )
    path_name = _find_main_nanoaod_path(process)
    if path_name:
        getattr(process, path_name).insert(0, getattr(process, filter_name))
    else:
        path_name = "disappTrks{}Skim_step".format(label)
        setattr(process, path_name, cms.Path(getattr(process, filter_name)))
        if hasattr(process, "schedule"):
            process.schedule.extend([getattr(process, path_name)])
    process = _select_output_events(process, path_name)
    process = _set_metadata(process, "customDisappTrksTriggerSkim", label)
    process = _set_metadata(process, "customDisappTrksTriggerPaths", ",".join(hlt_paths))
    return process


def AddDisappTrksMETTriggerSkim(process):
    return AddDisappTrksTriggerSkim(process, TABLE9_MET_HLT_PATHS, "MET")


def AddDisappTrksMuonTriggerSkim(process):
    return AddDisappTrksTriggerSkim(process, TABLE9_MUON_HLT_PATHS, "Muon")


def AddDisappTrksEGammaTriggerSkim(process):
    return AddDisappTrksTriggerSkim(process, TABLE9_EGAMMA_HLT_PATHS, "EGamma")
