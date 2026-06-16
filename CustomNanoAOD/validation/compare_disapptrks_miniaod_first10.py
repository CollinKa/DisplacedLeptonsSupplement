#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import ROOT
from DataFormats.FWLite import Events, Handle


MUON_FILTER = "hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered"
ELECTRON_FILTER = "hltEle32WPTightGsfTrackIsoFilter"

BRANCHES = [
    "metNoMu_pt",
    "metNoMu_phi",
    "muon_pfRelIso04_dBeta",
    "muon_isTrigMatched",
    "ele_isTrigMatched",
    "tau_isTight",
    "tau_decayModeFindingNewDMs",
    "jet_isTightLepVeto",
    "vtx_x",
    "vtx_y",
    "vtx_z",
    "vtx_ndof",
    "vtx_nTracks",
    "vtx_isValid",
    "vtx_isFake",
    "trk_pt",
    "trk_eta",
    "trk_phi",
    "trk_charge",
    "trk_dxy",
    "trk_dxyError",
    "trk_dz",
    "trk_dzError",
    "trk_fromPV",
    "trk_isHighPurityTrack",
    "trk_dEdxStrip",
    "trk_dEdxPixel",
    "trk_caloEm",
    "trk_caloHad",
    "trk_caloTotal",
    "trk_caloTotNoPU",
    "trk_pfIso",
    "trk_relativePFIso",
    "trk_missingInnerHits",
    "trk_missingOuterHits",
    "trk_hp_numberOfValidPixelHits",
    "trk_hp_trackerLayersWithMeasurement",
]


def delta_phi(a: float, b: float) -> float:
    dphi = a - b
    while dphi > math.pi:
        dphi -= 2.0 * math.pi
    while dphi <= -math.pi:
        dphi += 2.0 * math.pi
    return dphi


def delta_r(eta1: float, phi1: float, eta2: float, phi2: float) -> float:
    return math.hypot(eta1 - eta2, delta_phi(phi1, phi2))


def scalar_type(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "list[empty]"
        return "list[{}]".format(scalar_type(value[0]))
    return type(value).__name__


def to_python(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def leaf_value_to_python(value: Any, type_name: str) -> Any:
    if type_name == "Bool_t":
        return bool(value)
    if type_name in {"Char_t", "UChar_t", "Short_t", "UShort_t", "Int_t", "UInt_t", "Long64_t", "ULong64_t"}:
        return int(value)
    return float(value)


def branch_value_to_python(tree: Any, branch: str) -> Any:
    br = tree.GetBranch(branch)
    if not br:
        raise KeyError(branch)
    leaf = br.GetLeaf(branch) or br.GetListOfLeaves().At(0)
    type_name = leaf.GetTypeName()
    count_leaf = leaf.GetLeafCount()
    if count_leaf:
        count = int(count_leaf.GetValue())
        return [leaf_value_to_python(leaf.GetValue(i), type_name) for i in range(count)]
    return leaf_value_to_python(leaf.GetValue(), type_name)


def branch_type(tree: Any, branch: str) -> str:
    br = tree.GetBranch(branch)
    if not br:
        return "missing"
    if br.GetClassName():
        return br.GetClassName()
    leaf = br.GetLeaf(branch)
    return leaf.GetTypeName() if leaf else "unknown"


def close_enough(a: Any, b: Any, tolerance: float) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
            return False
        return all(close_enough(x, y, tolerance) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, int) and isinstance(b, int):
        return int(a) == int(b)
    try:
        af = float(a)
        bf = float(b)
    except Exception:
        return a == b
    scale = max(1.0, abs(af), abs(bf))
    return abs(af - bf) <= tolerance * scale


def max_abs_diff(a: Any, b: Any) -> float | None:
    diffs = []

    def collect(x: Any, y: Any) -> None:
        if isinstance(x, list) and isinstance(y, list):
            for xx, yy in zip(x, y):
                collect(xx, yy)
            return
        try:
            diffs.append(abs(float(x) - float(y)))
        except Exception:
            return

    collect(a, b)
    return max(diffs) if diffs else None


def get_product(event: Any, label: tuple[str, str, str] | str, handle: Handle) -> Any:
    event.getByLabel(label, handle)
    return handle.product()


def get_rho(event: Any, label: str, handle: Handle) -> float:
    event.getByLabel(label, handle)
    return float(handle.product()[0])


def trigger_eta_phi(event: Any, trigger_objects: Any, trigger_results: Any, filter_name: str) -> list[tuple[float, float]]:
    out = []
    for obj in trigger_objects:
        obj.unpackNamesAndLabels(event.object(), trigger_results)
        if obj.hasFilterLabel(filter_name):
            out.append((float(obj.eta()), float(obj.phi())))
    return out


def matched(obj: Any, refs: list[tuple[float, float]], max_dr: float = 0.3) -> bool:
    if not refs:
        return False
    return min(delta_r(float(obj.eta()), float(obj.phi()), eta, phi) for eta, phi in refs) < max_dr


def muon_pf_rel_iso_04_dbeta(mu: Any) -> float:
    iso = mu.pfIsolationR04()
    abs_iso = iso.sumChargedHadronPt + max(
        0.0, iso.sumNeutralHadronEt + iso.sumPhotonEt - 0.5 * iso.sumPUPt
    )
    return abs_iso / mu.pt() if mu.pt() > 0 else -1.0


def tau_id(tau: Any, name: str) -> float:
    try:
        return float(tau.tauID(name))
    except Exception:
        return -1.0


def tau_tight(tau: Any) -> bool:
    if tau_id(tau, "decayModeFindingNewDMs") <= 0.5:
        return False
    if tau.decayMode() in (5, 6):
        return False
    if tau_id(tau, "byVVVLooseDeepTau2018v2p5VSe") <= 0.5:
        return False
    if tau_id(tau, "byVLooseDeepTau2018v2p5VSmu") <= 0.5:
        return False
    return True


def jet_tight_lep_veto(jet: Any) -> bool:
    abs_eta = abs(float(jet.eta()))
    if abs_eta <= 2.6:
        return (
            jet.neutralHadronEnergyFraction() < 0.99
            and jet.neutralEmEnergyFraction() < 0.9
            and jet.numberOfDaughters() > 1
            and jet.muonEnergyFraction() < 0.8
            and jet.chargedHadronEnergyFraction() > 0.01
            and jet.chargedMultiplicity() > 0
            and jet.chargedEmEnergyFraction() < 0.8
        )
    if abs_eta <= 2.7:
        return (
            jet.neutralHadronEnergyFraction() < 0.9
            and jet.neutralEmEnergyFraction() < 0.99
            and jet.muonEnergyFraction() < 0.8
            and jet.chargedEmEnergyFraction() < 0.8
        )
    if abs_eta <= 3.0:
        return jet.neutralHadronEnergyFraction() < 0.99
    return jet.neutralEmEnergyFraction() < 0.4 and jet.neutralMultiplicity() >= 2


def build_snapshot(event: Any) -> dict[str, Any]:
    handles = {
        "muons": Handle("std::vector<pat::Muon>"),
        "vertices": Handle("std::vector<reco::Vertex>"),
        "tracks": Handle("std::vector<pat::IsolatedTrack>"),
        "electrons": Handle("std::vector<pat::Electron>"),
        "taus": Handle("std::vector<pat::Tau>"),
        "jets": Handle("std::vector<pat::Jet>"),
        "mets": Handle("std::vector<pat::MET>"),
        "rho": Handle("double"),
        "trigger_objects": Handle("std::vector<pat::TriggerObjectStandAlone>"),
        "trigger_results": Handle("edm::TriggerResults"),
    }
    muons = get_product(event, "slimmedMuons", handles["muons"])
    vertices = get_product(event, "offlineSlimmedPrimaryVertices", handles["vertices"])
    tracks = get_product(event, "isolatedTracks", handles["tracks"])
    electrons = get_product(event, "slimmedElectrons", handles["electrons"])
    taus = get_product(event, "slimmedTaus", handles["taus"])
    jets = get_product(event, "slimmedJets", handles["jets"])
    mets = get_product(event, "slimmedMETs", handles["mets"])
    rho_central_calo = get_rho(event, "fixedGridRhoFastjetCentralCalo", handles["rho"])
    trigger_objects = get_product(event, "slimmedPatTrigger", handles["trigger_objects"])
    trigger_results = get_product(event, ("TriggerResults", "", "HLT"), handles["trigger_results"])
    mu_refs = trigger_eta_phi(event, trigger_objects, trigger_results, MUON_FILTER)
    ele_refs = trigger_eta_phi(event, trigger_objects, trigger_results, ELECTRON_FILTER)

    met = mets[0]
    met_x = met.pt() * math.cos(met.phi())
    met_y = met.pt() * math.sin(met.phi())
    for mu in muons:
        met_x += mu.pt() * math.cos(mu.phi())
        met_y += mu.pt() * math.sin(mu.phi())

    hp_track = 0
    hp_inner = 1
    hp_outer = 2

    return {
        "metNoMu_pt": math.hypot(met_x, met_y),
        "metNoMu_phi": math.atan2(met_y, met_x),
        "muon_pfRelIso04_dBeta": [muon_pf_rel_iso_04_dbeta(mu) for mu in muons],
        "muon_isTrigMatched": [matched(mu, mu_refs) for mu in muons],
        "ele_isTrigMatched": [matched(ele, ele_refs) for ele in electrons],
        "tau_isTight": [tau_tight(tau) for tau in taus],
        "tau_decayModeFindingNewDMs": [tau_id(tau, "decayModeFindingNewDMs") > 0.5 for tau in taus],
        "jet_isTightLepVeto": [jet_tight_lep_veto(jet) for jet in jets],
        "vtx_x": [v.x() for v in vertices],
        "vtx_y": [v.y() for v in vertices],
        "vtx_z": [v.z() for v in vertices],
        "vtx_ndof": [v.ndof() for v in vertices],
        "vtx_nTracks": [v.nTracks() for v in vertices],
        "vtx_isValid": [v.isValid() for v in vertices],
        "vtx_isFake": [v.isFake() for v in vertices],
        "trk_pt": [t.pt() for t in tracks],
        "trk_eta": [t.eta() for t in tracks],
        "trk_phi": [t.phi() for t in tracks],
        "trk_charge": [t.charge() for t in tracks],
        "trk_dxy": [t.dxy() for t in tracks],
        "trk_dxyError": [t.dxyError() for t in tracks],
        "trk_dz": [t.dz() for t in tracks],
        "trk_dzError": [t.dzError() for t in tracks],
        "trk_fromPV": [t.fromPV() for t in tracks],
        "trk_isHighPurityTrack": [t.isHighPurityTrack() for t in tracks],
        "trk_dEdxStrip": [t.dEdxStrip() for t in tracks],
        "trk_dEdxPixel": [t.dEdxPixel() for t in tracks],
        "trk_caloEm": [t.matchedCaloJetEmEnergy() for t in tracks],
        "trk_caloHad": [t.matchedCaloJetHadEnergy() for t in tracks],
        "trk_caloTotal": [t.matchedCaloJetEmEnergy() + t.matchedCaloJetHadEnergy() for t in tracks],
        "trk_caloTotNoPU": [
            max(0.0, t.matchedCaloJetEmEnergy() + t.matchedCaloJetHadEnergy() - rho_central_calo * math.pi * 0.4 * 0.4)
            for t in tracks
        ],
        "trk_pfIso": [t.pfIsolationDR03().chargedHadronIso() for t in tracks],
        "trk_relativePFIso": [
            t.pfIsolationDR03().chargedHadronIso() / t.pt() if t.pt() > 0 else -1.0 for t in tracks
        ],
        "trk_missingInnerHits": [t.hitPattern().trackerLayersWithoutMeasurement(hp_inner) for t in tracks],
        "trk_missingOuterHits": [t.hitPattern().trackerLayersWithoutMeasurement(hp_outer) for t in tracks],
        "trk_hp_numberOfValidPixelHits": [t.hitPattern().numberOfValidPixelHits() for t in tracks],
        "trk_hp_trackerLayersWithMeasurement": [t.hitPattern().trackerLayersWithMeasurement() for t in tracks],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--miniaod", required=True)
    parser.add_argument("--nano", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--events", type=int, default=10)
    parser.add_argument("--tolerance", type=float, default=1.0e-5)
    args = parser.parse_args()

    root_file = ROOT.TFile.Open(args.nano)
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open {args.nano}")
    tree = root_file.Get("Events")
    if not tree:
        raise RuntimeError(f"Could not find Events tree in {args.nano}")
    tree_branches = {branch.GetName() for branch in tree.GetListOfBranches()}
    branches = [b for b in BRANCHES if b in tree_branches]
    branch_types = {b: branch_type(tree, b) for b in branches}

    nano_rows = []
    n_entries = min(args.events, int(tree.GetEntries()))
    for i in range(n_entries):
        tree.GetEntry(i)
        event_id = (int(tree.run), int(tree.luminosityBlock), int(tree.event))
        values = {branch: branch_value_to_python(tree, branch) for branch in branches}
        nano_rows.append((event_id, values))

    event_ids = [row[0] for row in nano_rows]
    wanted = set(event_ids)
    snapshots = {}
    events = Events(args.miniaod)
    for ev in events:
        aux = ev.eventAuxiliary()
        event_id = (int(aux.run()), int(aux.luminosityBlock()), int(aux.event()))
        if event_id in wanted:
            snapshots[event_id] = build_snapshot(ev)
            if len(snapshots) == len(wanted):
                break

    comparisons = []
    fail_count = 0
    checked_count = 0
    for event_id, nano_values in nano_rows:
        if event_id not in snapshots:
            comparisons.append({"event": event_id, "status": "FAIL", "reason": "event not found in MiniAOD"})
            fail_count += 1
            continue
        snap = snapshots[event_id]
        for branch in branches:
            custom_value = nano_values[branch]
            miniaod_value = snap[branch]
            ok = close_enough(custom_value, miniaod_value, args.tolerance)
            checked_count += 1
            fail_count += 0 if ok else 1
            comparisons.append(
                {
                    "event": event_id,
                    "branch": branch,
                    "status": "PASS" if ok else "FAIL",
                    "nano_type": str(branch_types[branch]),
                    "miniaod_type": scalar_type(miniaod_value),
                    "nano_length": len(custom_value) if isinstance(custom_value, list) else None,
                    "miniaod_length": len(miniaod_value) if isinstance(miniaod_value, list) else None,
                    "max_abs_diff": max_abs_diff(custom_value, miniaod_value),
                }
            )

    result = {
        "status": "PASS" if fail_count == 0 and len(event_ids) == args.events else "FAIL",
        "nano": args.nano,
        "miniaod": args.miniaod,
        "requested_events": args.events,
        "matched_events": len(snapshots),
        "compared_events": len(event_ids),
        "checked_values": checked_count,
        "failures": fail_count,
        "branches_checked": branches,
        "comparisons": comparisons,
    }
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "comparisons"}, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
