import FWCore.ParameterSet.Config as cms
from PhysicsTools.NanoAOD.common_cff import Var
# from DisplacedLeptonsSupplement.CustomNanoAOD.displacedMuons_cff import (
    # add_displaced_muons,
    # add_displaced_muon_timing,
    # add_displaced_muon_track_vars,
# )

CUSTOM_NANO_VERSION = 1


# Perigee parameter indices used by reco::TrackBase::covariance(i,j):
#   0 = q/p
#   1 = lambda  (= pi/2 - theta, the dip angle)
#   2 = phi
#   3 = dxy
#   4 = dsz     (= dz * cos(lambda), NOT dz)
_PERIGEE_PARAMS = ["qoverp", "lambda", "phi", "dxy", "dsz"]
_COV_INDICES = [(i, j) for i in range(5) for j in range(i, 5)]


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


def AddMuonTrackVars(process):
    t = process.muonTable.variables
    t.timeNdof = Var("time().nDof", int, doc="muon time ndof")
    t.timeAtIpInOut = Var("time().timeAtIpInOut", float, doc="muon time at IP (in-out) [ns]", precision=10)
    return process


def AddElectronTrackVars(process):
    t = process.electronTable.variables
    t.dxybs = Var("dB('BS2D')", float, doc="dxy (with sign) wrt the beam spot, in cm", precision=10),
    t.dxybsErr = Var("edB('BS2D')", float, doc="dxy uncertainty wrt the beam spot, in cm", precision=6)
    return process


def AddInMaterialVertices(process):
    """
    Fit all dilepton pairs (μμ, ee, eμ) with KalmanVertexFitter and write pairs
    that converge (chi2/ndof < 20) and land in tracker material to InMaterialVtx.

    Input collections are linkedObjects muons/electrons — the same collections
    that feed the NanoAOD Muon and Electron tables, so indices match exactly.

    Output branches: InMaterialVtx_{lep1Idx, lep2Idx, lep1Flavor, lep2Flavor}
    Flavor: 0 = muon, 1 = electron. For eμ pairs, lep1 is always the muon.
    """
    # TransientTrackBuilderESProducer is not loaded by the standard NanoAOD
    # sequence (only by full-reco sequences like PostRecoGenerator_cff).
    # It must be present for iSetup.get<TransientTrackRecord>() to succeed.
    if not hasattr(process, 'TransientTrackBuilderESProducer'):
        process.load("TrackingTools.TransientTrack.TransientTrackBuilder_cfi")

    process.inMaterialVertexTable = cms.EDProducer(
        "InMaterialVertexTableProducer",
        muons     = cms.InputTag("linkedObjects", "muons"),
        electrons = cms.InputTag("linkedObjects", "electrons"),
    )

    if hasattr(process, 'nanoTableTaskCommon'):
        process.nanoTableTaskCommon.add(process.inMaterialVertexTable)
    else:
        process.nanoSequenceCommon += process.inMaterialVertexTable

    return process


def PrepDisplacedLeptonsNanoAOD(process):
    # process = DropUnneededTasks(process)
    process = AddMuonTrackVars(process)
    process = AddElectronTrackVars(process)
    process = AddInMaterialVertices(process)
    # process = add_displaced_muons(process)
    # process = add_displaced_muon_timing(process)
    # process = add_displaced_muon_track_vars(process)
    process.nanoMetadata.strings.customNanoVersion = cms.string(str(CUSTOM_NANO_VERSION))
    return process
