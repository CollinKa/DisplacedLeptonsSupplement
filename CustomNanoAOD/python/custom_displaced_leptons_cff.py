import FWCore.ParameterSet.Config as cms
from PhysicsTools.NanoAOD.common_cff import Var
# from DisplacedLeptonsSupplement.CustomNanoAOD.displacedMuons_cff import (
    # add_displaced_muons,
    # add_displaced_muon_timing,
    # add_displaced_muon_track_vars,
# )

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
            "metTablesTask",
            "tauTablesTask",
            "boostedTauTablesTask",
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
      dxybs_db / dxybsErr_db       — cached dB(BS2D) from MiniAOD (wrong for Run 2, kept for reference)
      dxybs_track / dxybsErr_track — gsfTrack()->dxy(beamspot), analytic formula with tilt
      dxybs_iptools / dxybsErr_iptools — IPTools::signedTransverseImpactParameter
    """
    process.electronDxyBS = cms.EDProducer(
        "ElectronDxyBSProducer",
        electrons = cms.InputTag("linkedObjects", "electrons"),
        beamSpot  = cms.InputTag("offlineBeamSpot"),
    )

    if hasattr(process, 'nanoTableTaskCommon'):
        process.nanoTableTaskCommon.add(process.electronDxyBS)

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
    # process = add_displaced_muons(process)
    # process = add_displaced_muon_timing(process)
    # process = add_displaced_muon_track_vars(process)
    process.nanoMetadata.strings.customNanoVersion = cms.string(str(CUSTOM_NANO_VERSION))

    if not hasattr(process, 'nanoTableTaskCommon'):
        # CMSSW10: nanoSequenceCommon += rebinds the process attribute so the running
        # path never sees the addition. Use a dedicated Path + schedule.extend() instead,
        # which is the same pattern addMonitoring uses.
        _custom = [getattr(process, n) for n in
                   ('muonBFieldTable', 'electronBFieldTable', 'electronDxyBS', 'inMaterialVertexTable')
                   if hasattr(process, n)]
        if _custom:
            _seq = _custom[0]
            for _p in _custom[1:]:
                _seq = _seq + _p
            process.customDisplacedNano_step = cms.Path(_seq)
            process.schedule.extend([process.customDisplacedNano_step])

    return process
