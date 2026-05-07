import FWCore.ParameterSet.Config as cms
from PhysicsTools.NanoAOD.common_cff import Var


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
    """
    for task in [
        "photonTablesTask",
        "metTablesTask",
        "tauTablesTask",
        "boostedTauTablesTask",
        "jetPuppiTablesTask",
        "jetAK8TablesTask",
        "jetConstituentsTablesTask",
    ]:
        process.nanoTableTaskCommon.remove(getattr(process, task))

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
    t.innerTrack_vx = Var(
        "? innerTrack().isNonnull() ? innerTrack().vx() : -99",
        float, doc="inner track perigee reference point x [cm]", precision=-1)
    t.innerTrack_vy = Var(
        "? innerTrack().isNonnull() ? innerTrack().vy() : -99",
        float, doc="inner track perigee reference point y [cm]", precision=-1)
    t.innerTrack_vz = Var(
        "? innerTrack().isNonnull() ? innerTrack().vz() : -99",
        float, doc="inner track perigee reference point z [cm]", precision=-1)

    # Remaining perigee parameters (dxy/dz already in standard NanoAOD)
    t.innerTrack_qoverp = Var(
        "? innerTrack().isNonnull() ? innerTrack().qoverp() : -99",
        float, doc="inner track q/p [1/GeV]", precision=-1)
    t.innerTrack_lambda = Var(
        "? innerTrack().isNonnull() ? innerTrack().lambda() : -99",
        float, doc="inner track lambda = pi/2 - theta [rad]", precision=-1)
    t.innerTrack_dsz = Var(
        "? innerTrack().isNonnull() ? innerTrack().dsz() : -99",
        float, doc="inner track dsz = dz*cos(lambda) [cm]", precision=-1)

    # Full 5x5 covariance (upper triangle, 15 elements)
    for i, j in _COV_INDICES:
        name = f"innerTrack_cov_{_PERIGEE_PARAMS[i]}_{_PERIGEE_PARAMS[j]}"
        setattr(t, name, Var(
            f"? innerTrack().isNonnull() ? innerTrack().covariance({i},{j}) : -99",
            float,
            doc=f"inner track cov({_PERIGEE_PARAMS[i]}, {_PERIGEE_PARAMS[j]})",
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
    t.gsfTrack_vx = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().vx() : -99",
        float, doc="GSF track perigee reference point x [cm]", precision=-1)
    t.gsfTrack_vy = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().vy() : -99",
        float, doc="GSF track perigee reference point y [cm]", precision=-1)
    t.gsfTrack_vz = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().vz() : -99",
        float, doc="GSF track perigee reference point z [cm]", precision=-1)

    # Remaining perigee parameters
    t.gsfTrack_qoverp = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().qoverp() : -99",
        float, doc="GSF track q/p [1/GeV]", precision=-1)
    t.gsfTrack_lambda = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().lambda() : -99",
        float, doc="GSF track lambda = pi/2 - theta [rad]", precision=-1)
    t.gsfTrack_dsz = Var(
        "? gsfTrack().isNonnull() ? gsfTrack().dsz() : -99",
        float, doc="GSF track dsz = dz*cos(lambda) [cm]", precision=-1)

    # Full 5x5 covariance (upper triangle, 15 elements)
    for i, j in _COV_INDICES:
        name = f"gsfTrack_cov_{_PERIGEE_PARAMS[i]}_{_PERIGEE_PARAMS[j]}"
        setattr(t, name, Var(
            f"? gsfTrack().isNonnull() ? gsfTrack().covariance({i},{j}) : -99",
            float,
            doc=f"GSF track cov({_PERIGEE_PARAMS[i]}, {_PERIGEE_PARAMS[j]})",
            precision=-1))

    return process


def PrepDisplacedLeptonsNanoAOD(process):
    process = DropUnneededTasks(process)
    process = AddMuonTrackVars(process)
    process = AddElectronTrackVars(process)
    return process
