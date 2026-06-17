import FWCore.ParameterSet.Config as cms
from PhysicsTools.NanoAOD.common_cff import Var
from DisplacedLeptonsSupplement.CustomNanoAOD.displacedMuons_cff import add_displaced_muons
from DisplacedLeptonsSupplement.CustomNanoAOD.disapp_trks_cff import (
    AddDisappTrksEGammaTriggerSkim,
    AddDisappTrksMETTriggerSkim,
    AddDisappTrksMuonTriggerSkim,
    AddDisappTrksNanoTables,
)

CUSTOM_NANO_VERSION = 1


def DropUnneededTasks(process):
    """
    Remove tables not relevant to a displaced dilepton analysis.
    Keeps muons, electrons, vertices, tracks, triggers, and PF candidates.

    Run 3 uses a task-based system (nanoTableTaskCommon); Run 2 uses a sequence
    (nanoSequenceCommon). In the Run 2 case we only remove the table-producing
    modules, not the upstream producer sequences, because linkedObjects still
    needs finalTaus, finalPhotons, etc. to be present.
    """
    if hasattr(process, 'nanoTableTaskCommon'):
        # Run 3
        for name in [
            "photonTablesTask",
            "photonTask",
            "metTablesTask",
            "tauTablesTask",
            "tauTask",
            "boostedTauTablesTask",
            "boostedTauTask",
            "jetPuppiTablesTask",
            "jetAK8TablesTask",
            "jetConstituentsTablesTask",
        ]:
            if hasattr(process, name):
                process.nanoTableTaskCommon.remove(getattr(process, name))
    else:
        for name in [
            "photonTables",
            "photonMC",
            "metTables",
            "metMC",
            "tauTables",
            "tauMC",
            "isoTrackTables",
            "isoTrackSequence",
            "particleLevelTables",
            "simpleCleanerTable",
        ]:
            if hasattr(process, name):
                for seq_name in ['nanoSequenceMC', 'nanoSequenceFS', 'nanoSequenceCommon']:
                    if hasattr(process, seq_name):
                        try:
                            getattr(process, seq_name).remove(getattr(process, name))
                        except Exception:
                            pass  # not present in this sequence or already excluded by era modifier

    return process


def _remove_module_from_sequence(process, sequence_name, module_name):
    if not hasattr(process, sequence_name) or not hasattr(process, module_name):
        return
    try:
        getattr(process, sequence_name).remove(getattr(process, module_name))
    except Exception:
        pass


def _remove_module_from_task(process, task_name, module_name):
    if not hasattr(process, task_name) or not hasattr(process, module_name):
        return
    try:
        getattr(process, task_name).remove(getattr(process, module_name))
    except Exception:
        pass


def _keep_only_pset_parameters(pset, keep):
    keep = set(keep)
    for name in list(pset.parameters_().keys()):
        if name not in keep:
            delattr(pset, name)


def ApplyDisappTrksRun3MiniAODCompatibility(process):
    """
    Remove optional standard NanoAOD pieces that are incompatible with the
    Run 3 MiniAOD samples used for disappTrks custom NanoAOD production.

    This keeps the standard Muon, Electron, Jet, Vertex, and IsoTrack tables
    needed by downstream DLS NanoAOD analysis while avoiding known CMSSW15
    failures from LHCInfo, optional PUPPI jet columns, and unavailable
    electron VID value maps.
    """
    process = DropUnneededTasks(process)

    if hasattr(process, "nanoTableTaskCommon"):
        for task_name in ("jetTask", "jetTablesTask"):
            if hasattr(process, task_name):
                process.nanoTableTaskCommon.add(getattr(process, task_name))

    for sequence_name in ("nanoSequence", "nanoSequenceOnlyData"):
        _remove_module_from_sequence(process, sequence_name, "lhcInfoTable")

    if hasattr(process, "jetPuppiTable") and hasattr(process.jetPuppiTable.variables, "puIdDisc"):
        del process.jetPuppiTable.variables.puIdDisc
    if hasattr(process, "jetTable"):
        _keep_only_pset_parameters(process.jetTable.variables, ("pt", "eta", "phi"))
        if hasattr(process.jetTable, "externalVariables"):
            _keep_only_pset_parameters(process.jetTable.externalVariables, ())
    for module_name in ("bjetNN", "cjetNN"):
        _remove_module_from_task(process, "jetTablesTask", module_name)

    if hasattr(process, "linkedObjects"):
        for name, tag in (
            ("boostedTaus", "slimmedTaus"),
            ("photons", "slimmedPhotons"),
            ("taus", "slimmedTaus"),
        ):
            if hasattr(process.linkedObjects, name):
                setattr(process.linkedObjects, name, cms.InputTag(tag))

    for module_name in ("bitmapVIDForEle", "bitmapVIDForEleFall17V2", "bitmapVIDForEleHEEP"):
        _remove_module_from_task(process, "electronTask", module_name)
    _remove_module_from_task(process, "electronTablesTask", "electronPROMPTMVA")

    if hasattr(process, "slimmedElectronsWithUserData"):
        for name in (
            "mvaIso_Fall17V2",
            "mvaNoIso_Fall17V2",
            "mvaIso",
            "mvaNoIso",
            "mvaHZZIso",
        ):
            if hasattr(process.slimmedElectronsWithUserData.userFloats, name):
                delattr(process.slimmedElectronsWithUserData.userFloats, name)
        for name in (
            "mvaIso_Fall17V2_WP90",
            "mvaIso_Fall17V2_WP80",
            "mvaIso_Fall17V2_WPL",
            "mvaIso_WP90",
            "mvaIso_WP80",
            "mvaNoIso_Fall17V2_WP90",
            "mvaNoIso_Fall17V2_WP80",
            "mvaNoIso_Fall17V2_WPL",
            "mvaNoIso_WP90",
            "mvaNoIso_WP80",
            "mvaIso_WPHZZ",
            "cutBasedID_veto",
            "cutBasedID_loose",
            "cutBasedID_medium",
            "cutBasedID_tight",
            "cutBasedID_Fall17V2_veto",
            "cutBasedID_Fall17V2_loose",
            "cutBasedID_Fall17V2_medium",
            "cutBasedID_Fall17V2_tight",
            "cutBasedID_HEEP",
        ):
            if hasattr(process.slimmedElectronsWithUserData.userIntFromBools, name):
                delattr(process.slimmedElectronsWithUserData.userIntFromBools, name)
        for name in ("VIDNestedWPBitmap", "VIDNestedWPBitmap_Fall17V2", "VIDNestedWPBitmapHEEP"):
            if hasattr(process.slimmedElectronsWithUserData.userInts, name):
                delattr(process.slimmedElectronsWithUserData.userInts, name)

    if hasattr(process, "electronTable"):
        if hasattr(process.electronTable, "externalVariables") and hasattr(process.electronTable.externalVariables, "promptMVA"):
            delattr(process.electronTable.externalVariables, "promptMVA")
        for name in (
            "cutBased",
            "cutBased_Fall17V2",
            "cutBased_HEEP",
            "mvaIso",
            "mvaIso_WP80",
            "mvaIso_WP90",
            "mvaNoIso",
            "mvaNoIso_WP80",
            "mvaNoIso_WP90",
            "mvaHZZIso",
            "mvaIso_WPHZZ",
            "promptMVA",
            "vidNestedWPBitmap",
            "vidNestedWPBitmapHEEP",
        ):
            if hasattr(process.electronTable.variables, name):
                delattr(process.electronTable.variables, name)

    return process


def AddMuonVars(process):
    t = process.muonTable.variables

    t.pfIso04_sumChargedHadronPt = Var(
        "pfIsolationR04().sumChargedHadronPt",
        float,
        doc="PF isolation R=0.4, charged hadron pT sum [GeV]",
        precision=10
    )
    t.pfIso04_sumPUPt = Var(
        "pfIsolationR04().sumPUPt",
        float,
        doc="PF isolation R=0.4, PU charged hadron pT sum [GeV]",
        precision=10
    )
    t.pfIso04_sumNeutral = Var(
        "pfIsolationR04().sumNeutralHadronEt + pfIsolationR04().sumPhotonEt",
        float,
        doc="PF isolation R=0.4, neutral hadron + photon ET sum [GeV]",
        precision=10
    )

    t.timeNdof = Var("time().nDof", int, doc="muon time ndof")
    t.timeAtIpInOut = Var("time().timeAtIpInOut", float, doc="muon time at IP (in-out) [ns]", precision=10)
    return process


def AddElectronVars(process):
    t = process.electronTable.variables

    t.pfIso03_sumChargedHadronPt = Var(
        "pfIsolationVariables().sumChargedHadronPt",
        float,
        doc="PF isolation R=0.3, charged hadron pT sum [GeV]",
        precision=10
    )
    t.pfIso03_sumPUPt = Var(
        "pfIsolationVariables().sumPUPt",
        float,
        doc="PF isolation R=0.3, PU charged hadron pT sum [GeV]",
        precision=10
    )
    t.pfIso03_sumNeutral = Var(
        "pfIsolationVariables().sumNeutralHadronEt + pfIsolationVariables().sumPhotonEt",
        float,
        doc="PF isolation R=0.3, neutral hadron + photon ET sum [GeV]",
        precision=10
    )
    return process


def AddElectronDxyBS(process):
    """
    Add correct beamspot-relative electron d0 via three methods to the Electron table.
    Replaces the broken dB('BS2D') Var, which was computed wrt the origin (0,0,0)
    in all Run 2 MiniAOD due to a bug in CMSSW_9_4_5 PATElectronProducer.

    Branches added (all in cm):
      dxybs / dxybsErr  - gsfTrack()->dxy(beamspot), analytic formula with tilt
    """
    process.electronDxyBSTable = cms.EDProducer(
        "ElectronDxyBSProducer",
        electrons = cms.InputTag("linkedObjects", "electrons"),
        beamSpot  = cms.InputTag("offlineBeamSpot"),
    )

    if hasattr(process, 'nanoTableTaskCommon'):
        process.nanoTableTaskCommon.add(process.electronDxyBSTable)

    return process


def AddInMaterialVertices(process):
    """
    Fit all dilepton pairs (mumu, ee, emu) with KalmanVertexFitter and write pairs
    that converge (chi2/ndof < 20) and land in tracker material to InMaterialVtx.

    Input collections are linkedObjects muons/electrons - the same collections
    that feed the NanoAOD Muon and Electron tables, so indices match exactly.

    Output branches: InMaterialVtx_{lep1Idx, lep2Idx, lep1Flavor, lep2Flavor}
    Flavor: 0 = muon, 1 = electron. For emu pairs, lep1 is always the muon.
    """
    # TransientTrackBuilderESProducer is not loaded by the standard NanoAOD
    # sequence (only by full-reco sequences like PostRecoGenerator_cff).
    # It must be present for iSetup.get<TransientTrackRecord>() to succeed.
    # if not hasattr(process, 'TransientTrackBuilderESProducer'):
        # process.load("TrackingTools.TransientTrack.TransientTrackBuilder_cfi")

    process.inMaterialVertexTable = cms.EDProducer(
        "InMaterialVertexTableProducer",
        muons     = cms.InputTag("linkedObjects", "muons"),
        electrons = cms.InputTag("linkedObjects", "electrons"),
    )

    if hasattr(process, 'nanoTableTaskCommon'):
        process.nanoTableTaskCommon.add(process.inMaterialVertexTable)
    # Run 2: scheduled in PrepDisplacedLeptonsNanoAOD via a dedicated path.

    return process


def PrepDisplacedLeptonsNanoAOD(process):
    # process = DropUnneededTasks(process)
    process = AddMuonVars(process)
    process = AddElectronVars(process)
    process = AddElectronDxyBS(process)
    process = AddInMaterialVertices(process)
    process = add_displaced_muons(process)
    process.nanoMetadata.strings.customNanoVersion = cms.string(str(CUSTOM_NANO_VERSION))

    if not hasattr(process, 'nanoTableTaskCommon'):
        # CMSSW10: nanoSequenceCommon += rebinds the process attribute so the running
        # path never sees the addition. Use a dedicated Path + schedule.extend() instead,
        # which is the same pattern addMonitoring uses.
        _custom = [getattr(process, n) for n in
                   ('muonBFieldTable', 'electronBFieldTable', 'electronDxyBSTable', 'inMaterialVertexTable')
                   if hasattr(process, n)]
        if _custom:
            _seq = _custom[0]
            for _p in _custom[1:]:
                _seq = _seq + _p
            process.customDisplacedNano_step = cms.Path(_seq)
            process.schedule.extend([process.customDisplacedNano_step])

    return process


def PrepDisplacedLeptonsDisappTrksNanoAOD(process):
    process = PrepDisplacedLeptonsNanoAOD(process)
    process = AddDisappTrksNanoTables(process)
    return process


def PrepDisplacedLeptonsDisappTrksNanoAOD_METSkim(process):
    process = PrepDisplacedLeptonsDisappTrksNanoAOD(process)
    process = AddDisappTrksMETTriggerSkim(process)
    return process


def PrepDisplacedLeptonsDisappTrksNanoAOD_MuonSkim(process):
    process = PrepDisplacedLeptonsDisappTrksNanoAOD(process)
    process = AddDisappTrksMuonTriggerSkim(process)
    return process


def PrepDisplacedLeptonsDisappTrksNanoAOD_EGammaSkim(process):
    process = PrepDisplacedLeptonsDisappTrksNanoAOD(process)
    process = AddDisappTrksEGammaTriggerSkim(process)
    return process
