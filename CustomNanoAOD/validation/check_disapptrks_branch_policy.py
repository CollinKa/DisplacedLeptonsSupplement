#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ROOT


DISALLOWED_DUPLICATE_MAP = {
    "muon_pt": "Muon_pt",
    "muon_eta": "Muon_eta",
    "muon_phi": "Muon_phi",
    "muon_charge": "Muon_charge",
    "muon_isTight": "Muon_tightId",
    "ele_pt": "Electron_pt",
    "ele_eta": "Electron_eta",
    "ele_phi": "Electron_phi",
    "ele_charge": "Electron_charge",
    "ele_isTight": "Electron_cutBased",
    "tau_pt": "Tau_pt",
    "tau_eta": "Tau_eta",
    "tau_phi": "Tau_phi",
    "tau_charge": "Tau_charge",
    "tau_decayMode": "Tau_decayMode",
    "tau_deepTau2018v2p5VSjet": "Tau_rawDeepTau2018v2p5VSjet",
    "tau_deepTau2018v2p5VSe": "Tau_rawDeepTau2018v2p5VSe",
    "tau_deepTau2018v2p5VSmu": "Tau_rawDeepTau2018v2p5VSmu",
    "jet_pt": "Jet_pt",
    "jet_eta": "Jet_eta",
    "jet_phi": "Jet_phi",
    "jet_energy": "Jet_mass",
    "met_pt": "MET_pt",
    "met_phi": "MET_phi",
    "rho_all": "Rho_fixedGridRhoFastjetAll",
    "rho_centralCalo": "Rho_fixedGridRhoFastjetCentralCalo",
}

EXPECTED_DISAPPTRKS_ADDITIONS = {
    "metNoMu_pt",
    "metNoMu_phi",
    "muon_isTrigMatched",
    "muon_pfRelIso04_dBeta",
    "ele_isTrigMatched",
    "tau_isTight",
    "tau_decayModeFindingNewDMs",
    "jet_isTightLepVeto",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nano", required=True)
    parser.add_argument("--central-branches", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    central = {
        line.strip()
        for line in Path(args.central_branches).read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }

    root_file = ROOT.TFile.Open(args.nano)
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open {args.nano}")
    tree = root_file.Get("Events")
    if not tree:
        raise RuntimeError(f"Could not find Events tree in {args.nano}")
    branches = {branch.GetName() for branch in tree.GetListOfBranches()}

    disallowed_present = {
        custom: central_name
        for custom, central_name in DISALLOWED_DUPLICATE_MAP.items()
        if custom in branches and central_name in central
    }

    expected_present = sorted(EXPECTED_DISAPPTRKS_ADDITIONS & branches)
    expected_missing = sorted(EXPECTED_DISAPPTRKS_ADDITIONS - branches)
    trk_additions = sorted(b for b in branches if b.startswith("trk_"))
    vtx_additions = sorted(b for b in branches if b.startswith("vtx_"))

    result = {
        "status": "PASS" if not disallowed_present and not expected_missing else "FAIL",
        "nano": args.nano,
        "central_branches": args.central_branches,
        "n_branches": len(branches),
        "disallowed_duplicate_count": len(disallowed_present),
        "disallowed_duplicates": disallowed_present,
        "expected_disapptrks_additions_present": expected_present,
        "expected_disapptrks_additions_missing": expected_missing,
        "n_trk_branches": len(trk_additions),
        "n_vtx_branches": len(vtx_additions),
        "trk_source_note": (
            "trk_* is kept as a separate raw isolatedTracks-derived table. "
            "Central IsoTrack_* uses finalIsolatedTracks after NanoAOD cleaning, so it is not treated as an exact duplicate."
        ),
    }
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
