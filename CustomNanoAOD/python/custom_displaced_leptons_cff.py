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
    """
    Add to the muon table:
      - inner track reference point (vx, vy, vz)
      - full 5x5 inner track covariance matrix (15 upper-triangle elements)
      - perigee parameters not already in NanoAOD (qoverp, lambda, dsz)

    These are the quantities needed to run KalmanVertexFitter in Python.
    dxy and dz are already in standard NanoAOD; dsz = dz*cos(lambda) is stored
    here instead of dz because that is the native 5th perigee parameter.
    """
    t = process.muonTable.variables

    # Reference point
    t.track_vx = Var(
        "? innerTrack().isNonnull() ? innerTrack().vx() : -99",
        float, doc="inner track perigee reference point x [cm]", precision=-1)
    t.track_vy = Var(
        "? innerTrack().isNonnull() ? innerTrack().vy() : -99",
        float, doc="inner track perigee reference point y [cm]", precision=-1)
    t.track_vz = Var(
        "? innerTrack().isNonnull() ? innerTrack().vz() : -99",
        float, doc="inner track perigee reference point z [cm]", precision=-1)

    # Remaining perigee parameters (dxy/dz already in standard NanoAOD)
    t.track_qoverp = Var(
        "? innerTrack().isNonnull() ? innerTrack().qoverp() : -99",
        float, doc="inner track q/p [1/GeV]", precision=-1)
    t.track_lambda = Var(
        "? innerTrack().isNonnull() ? innerTrack().lambda() : -99",
        float, doc="inner track lambda = pi/2 - theta [rad]", precision=-1)
    t.track_dsz = Var(
        "? innerTrack().isNonnull() ? innerTrack().dsz() : -99",
        float, doc="inner track dsz = dz*cos(lambda) [cm]", precision=-1)

    # Full 5x5 covariance (upper triangle, 15 elements)
    for i, j in _COV_INDICES:
        name = "track_cov_{}_{}".format(_PERIGEE_PARAMS[i], _PERIGEE_PARAMS[j])
        setattr(t, name, Var(
            "? innerTrack().isNonnull() ? innerTrack().covariance({},{}) : -99".format(i, j),
            float,
            doc="inner track cov({}, {})".format(_PERIGEE_PARAMS[i], _PERIGEE_PARAMS[j]),
            precision=-1))

    # Timing
    t.timeNdof = Var("time().nDof", int, doc="muon time ndof")
    t.timeAtIpInOut = Var("time().timeAtIpInOut", float, doc="muon time at IP (in-out) [ns]", precision=10)

    return process


def AddElectronTrackVars(process):
    """
    Add to the electron table:
      - GSF track reference point (vx, vy, vz)
      - full 5x5 GSF track covariance matrix (15 upper-triangle elements)
      - perigee parameters not already in NanoAOD (qoverp, lambda, dsz)

    The GSF track covariance and parameters represent the mode of the Gaussian
    mixture, which is what KalmanVertexFitter uses internally.
    """
    t = process.electronTable.variables

    # Reference point
    t.track_vx = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().vx() : -99",
        float, doc="GSF track perigee reference point x [cm]", precision=-1)
    t.track_vy = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().vy() : -99",
        float, doc="GSF track perigee reference point y [cm]", precision=-1)
    t.track_vz = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().vz() : -99",
        float, doc="GSF track perigee reference point z [cm]", precision=-1)

    # Remaining perigee parameters
    t.track_qoverp = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().qoverp() : -99",
        float, doc="GSF track q/p [1/GeV]", precision=-1)
    t.track_lambda = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().lambda() : -99",
        float, doc="GSF track lambda = pi/2 - theta [rad]", precision=-1)
    t.track_dsz = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().dsz() : -99",
        float, doc="GSF track dsz = dz*cos(lambda) [cm]", precision=-1)

    # Full 5x5 covariance (upper triangle, 15 elements)
    for i, j in _COV_INDICES:
        name = "track_cov_{}_{}".format(_PERIGEE_PARAMS[i], _PERIGEE_PARAMS[j])
        setattr(t, name, Var(
            "? gsfTrack().isNonnull() ? gsfTrack().covariance({},{}) : -99".format(i, j),
            float,
            doc="GSF track cov({}, {})".format(_PERIGEE_PARAMS[i], _PERIGEE_PARAMS[j]),
            precision=-1))

    return process


def PrepDisplacedLeptonsNanoAOD(process):
    # process = DropUnneededTasks(process)
    process = AddMuonTrackVars(process)
    process = AddElectronTrackVars(process)
    # process = add_displaced_muons(process)
    # process = add_displaced_muon_timing(process)
    # process = add_displaced_muon_track_vars(process)
    process.nanoMetadata.strings.customNanoVersion = cms.string(str(CUSTOM_NANO_VERSION))
    return process
