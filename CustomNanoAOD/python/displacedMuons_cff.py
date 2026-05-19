import FWCore.ParameterSet.Config as cms

from PhysicsTools.NanoAOD.common_cff import *
from PhysicsTools.NanoAOD.simplePATMuonFlatTableProducer_cfi import simplePATMuonFlatTableProducer

_PERIGEE_PARAMS = ["qoverp", "lambda", "phi", "dxy", "dsz"]
_COV_INDICES = [(i, j) for i in range(5) for j in range(i, 5)]


def add_displaced_muons(process):
    process.finalDisplacedMuons = cms.EDFilter("PATMuonRefSelector",
        src = cms.InputTag("slimmedDisplacedMuons"),
        cut = cms.string("pt > 15")
    )

    process.displacedMuonTable = simplePATMuonFlatTableProducer.clone(
        src = cms.InputTag("finalDisplacedMuons"),
        name = cms.string("DisplacedMuon"),
        doc = cms.string("slimmedDisplacedMuons after basic selection (" + process.finalDisplacedMuons.cut.value() + ")"),
        variables = cms.PSet(CandVars,
            ptErr          = Var("bestTrack().ptError()", float, doc="ptError of the muon track", precision=6),
            dz             = Var("dB('PVDZ')", float, doc="dz (with sign) wrt first PV, in cm", precision=10),
            dzErr          = Var("abs(edB('PVDZ'))", float, doc="dz uncertainty, in cm", precision=6),
            dxy            = Var("dB('PV2D')", float, doc="dxy (with sign) wrt first PV, in cm", precision=10),
            dxyErr         = Var("edB('PV2D')", float, doc="dxy uncertainty, in cm", precision=6),
            dxybs          = Var("dB('BS2D')", float, doc="dxy (with sign) wrt the beam spot, in cm", precision=10),
            dxybsErr       = Var("edB('BS2D')", float, doc="dxy uncertainty wrt the beam spot, in cm", precision=6),
            ip3d           = Var("abs(dB('PV3D'))", float, doc="3D impact parameter wrt first PV, in cm", precision=10),
            sip3d          = Var("abs(dB('PV3D')/edB('PV3D'))", float, doc="3D impact parameter significance wrt first PV", precision=10),
            segmentComp    = Var("segmentCompatibility()", float, doc="muon segment compatibility", precision=14),
            nStations      = Var("numberOfMatchedStations", "uint8", doc="number of matched stations with default arbitration (segment & track)"),
            nTrackerLayers = Var("?track.isNonnull?innerTrack().hitPattern().trackerLayersWithMeasurement():0", "uint8", doc="number of layers in the tracker"),
            bestTrackType  = Var("muonBestTrackType()", "uint8", doc="type of track used (1=inner, 2=STA, 3=global, 4=TPFMS, 5=Picky, 6=DYT)"),
            highPurity     = Var("?track.isNonnull?innerTrack().quality('highPurity'):0", bool, doc="inner track is high purity"),
            tightCharge    = Var("?(muonBestTrack().ptError()/muonBestTrack().pt() < 0.2)?2:0", "uint8", doc="tight charge criterion using pterr/pt of muonBestTrack (0:fail, 2:pass)"),
            isPFcand       = Var("isPFMuon", bool, doc="muon is PF candidate"),
            isGlobal       = Var("isGlobalMuon", bool, doc="muon is global muon"),
            isTracker      = Var("isTrackerMuon", bool, doc="muon is tracker muon"),
            isStandalone   = Var("isStandAloneMuon", bool, doc="muon is a standalone muon"),
            pfRelIso03_chg = Var("pfIsolationR03().sumChargedHadronPt/pt", float, doc="PF relative isolation dR=0.3, charged component"),
            pfRelIso03_all = Var("(pfIsolationR03().sumChargedHadronPt + max(pfIsolationR03().sumNeutralHadronEt + pfIsolationR03().sumPhotonEt - pfIsolationR03().sumPUPt/2,0.0))/pt", float, doc="PF relative isolation dR=0.3, total (deltaBeta corrections)"),
            pfRelIso04_all = Var("(pfIsolationR04().sumChargedHadronPt + max(pfIsolationR04().sumNeutralHadronEt + pfIsolationR04().sumPhotonEt - pfIsolationR04().sumPUPt/2,0.0))/pt", float, doc="PF relative isolation dR=0.4, total (deltaBeta corrections)"),
        ),
    )

    # increase precision of eta and phi to match standard muon table
    process.displacedMuonTable.variables.eta.precision = 16
    process.displacedMuonTable.variables.phi.precision = 16

    process.displacedMuonTask = cms.Task(process.finalDisplacedMuons)
    process.displacedMuonTablesTask = cms.Task(process.displacedMuonTable)

    process.nanoTableTaskCommon.add(process.displacedMuonTask)
    process.nanoTableTaskCommon.add(process.displacedMuonTablesTask)

    return process


def add_displaced_muon_timing(process):
    t = process.displacedMuonTable.variables
    t.timeNdof         = Var("time().nDof", int, doc="combined DT+CSC timing ndof")
    t.timeAtIpInOut    = Var("time().timeAtIpInOut", float, doc="combined DT+CSC time at IP (in-out) [ns]", precision=10)
    t.timeAtIpInOutErr = Var("time().timeAtIpInOutErr", float, doc="combined DT+CSC time at IP (in-out) uncertainty [ns]", precision=10)
    t.timeAtIpOutIn    = Var("time().timeAtIpOutIn", float, doc="combined DT+CSC time at IP (out-in) [ns]", precision=10)
    t.timeAtIpOutInErr = Var("time().timeAtIpOutInErr", float, doc="combined DT+CSC time at IP (out-in) uncertainty [ns]", precision=10)
    t.rpcTimeNdof         = Var("rpcTime().nDof", int, doc="RPC timing ndof")
    t.rpcTimeAtIpInOut    = Var("rpcTime().timeAtIpInOut", float, doc="RPC time at IP (in-out) [ns]", precision=10)
    t.rpcTimeAtIpInOutErr = Var("rpcTime().timeAtIpInOutErr", float, doc="RPC time at IP (in-out) uncertainty [ns]", precision=10)
    return process


def add_displaced_muon_track_vars(process):
    t = process.displacedMuonTable.variables
    t.track_vx = Var("? innerTrack().isNonnull() ? innerTrack().vx() : -99",
        float, doc="inner track perigee reference point x [cm]", precision=-1)
    t.track_vy = Var("? innerTrack().isNonnull() ? innerTrack().vy() : -99",
        float, doc="inner track perigee reference point y [cm]", precision=-1)
    t.track_vz = Var("? innerTrack().isNonnull() ? innerTrack().vz() : -99",
        float, doc="inner track perigee reference point z [cm]", precision=-1)
    t.track_qoverp = Var("? innerTrack().isNonnull() ? innerTrack().qoverp() : -99",
        float, doc="inner track q/p [1/GeV]", precision=-1)
    t.track_lambda = Var("? innerTrack().isNonnull() ? innerTrack().lambda() : -99",
        float, doc="inner track lambda = pi/2 - theta [rad]", precision=-1)
    t.track_dsz = Var("? innerTrack().isNonnull() ? innerTrack().dsz() : -99",
        float, doc="inner track dsz = dz*cos(lambda) [cm]", precision=-1)
    for i, j in _COV_INDICES:
        name = "track_cov_{}_{}".format(_PERIGEE_PARAMS[i], _PERIGEE_PARAMS[j])
        setattr(t, name, Var(
            "? innerTrack().isNonnull() ? innerTrack().covariance({},{}) : -99".format(i, j),
            float,
            doc="inner track cov({}, {})".format(_PERIGEE_PARAMS[i], _PERIGEE_PARAMS[j]),
            precision=-1))
    return process
