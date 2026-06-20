from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable

import awkward as ak
import numpy as np
import vector

vector.register_awkward()

MUON_MASS = 0.105658
Z_MASS = 91.1876
LAYERS = ("NLayers4", "NLayers5", "NLayers6plus", "combinedBins")
MUON_TRIGGER_MATCHING_DR = 0.3
MUON_TRIGOBJ_ID = 13
MUON_ISOMU24_STANDARD_NANOAOD_FILTER_BIT = 3

# Canonical DLS names are kept in the analysis code.  The aliases let the same
# Pveto code read OSUNano-style central branches without duplicating the logic.
BRANCH_ALIASES = {
    "metNoMu_pt": ("MetNoMu_pt",),
    "metNoMu_phi": ("MetNoMu_phi",),
    "muon_isTrigMatched": ("Muon_isTrigMatched",),
    "Electron_eta": ("RawElectron_eta", "Electron_eta"),
    "Electron_phi": ("RawElectron_phi", "Electron_phi"),
    "trk_pt": ("RawIsoTrack_pt", "IsoTrack_pt"),
    "trk_eta": ("RawIsoTrack_eta", "IsoTrack_eta"),
    "trk_phi": ("RawIsoTrack_phi", "IsoTrack_phi"),
    "trk_theta": ("RawIsoTrack_theta", "IsoTrack_theta"),
    "trk_charge": ("RawIsoTrack_charge", "IsoTrack_charge"),
    "trk_dxy": ("RawIsoTrack_dxy", "IsoTrack_dxy"),
    "trk_dz": ("RawIsoTrack_dz", "IsoTrack_dz"),
    "trk_missingInnerHits": ("RawIsoTrack_missingInnerHits", "IsoTrack_missingInnerHits"),
    "trk_hitDrop_missingMiddleHits": ("RawIsoTrack_missingMiddleHits", "IsoTrack_missingMiddleHits"),
    "trk_missingOuterHits": ("RawIsoTrack_missingOuterHits", "IsoTrack_missingOuterHits"),
    "trk_relativePFIso": ("RawIsoTrack_pfRelIso03_chg", "RawIsoTrack_pfRelIso03_all", "IsoTrack_pfRelIso03_chg", "IsoTrack_pfRelIso03_all"),
    "trk_hp_numberOfValidPixelHits": ("RawIsoTrack_hp_nValidPixelHits", "IsoTrack_hp_nValidPixelHits"),
    "trk_hp_trackerLayersWithMeasurement": ("RawIsoTrack_hp_trackerLayersWithMeasurement", "IsoTrack_hp_trackerLayersWithMeasurement"),
    "trk_caloTotal": ("RawIsoTrack_caloTotal", "IsoTrack_caloTotal"),
    "Jet_pt": ("RawJet_pt", "Jet_pt"),
    "Jet_eta": ("RawJet_eta", "Jet_eta"),
    "Jet_phi": ("RawJet_phi", "Jet_phi"),
    "jet_isTightLepVeto": ("RawJet_isTightLepVeto", "Jet_isTightLepVeto"),
}

COMPUTED_BRANCH_REQUIREMENTS = {
    "trk_caloTotNoPU": (
        "trk_caloTotal",
        "Rho_fixedGridRhoFastjetCentralCalo",
    ),
    "jet_isTightLepVeto": (
        "Jet_neHEF",
        "Jet_neEmEF",
        "Jet_nConstituents",
        "Jet_muEF",
        "Jet_chHEF",
        "Jet_chMultiplicity",
        "Jet_chEmEF",
        "Jet_neMultiplicity",
    ),
}

OPTIONAL_BRANCHES = (
    "muon_isTrigMatched",
    "jet_isTightLepVeto",
    "TrigObj_id",
    "TrigObj_filterBits",
    "TrigObj_eta",
    "TrigObj_phi",
)

PVETO_BRANCHES = [
    "metNoMu_pt",
    "metNoMu_phi",
    "HLT_IsoMu24",
    "Muon_pt",
    "Muon_eta",
    "Muon_phi",
    "Muon_charge",
    "Muon_tightId",
    "Electron_eta",
    "Electron_phi",
    "Jet_eta",
    "Jet_phi",
    "Jet_pt",
    "jet_isTightLepVeto",
    "trk_pt",
    "trk_eta",
    "trk_phi",
    "trk_theta",
    "trk_charge",
    "trk_dxy",
    "trk_dz",
    "trk_missingInnerHits",
    "trk_hitDrop_missingMiddleHits",
    "trk_missingOuterHits",
    "trk_relativePFIso",
    "trk_caloTotNoPU",
    "trk_hp_numberOfValidPixelHits",
    "trk_hp_trackerLayersWithMeasurement",
]

REQUIRED_BRANCHES = tuple(PVETO_BRANCHES)

BRANCH_NOTES = {
    "trk_caloTotNoPU": (
        "For OSUNano inputs this is reconstructed from IsoTrack_caloTotal and "
        "Rho_fixedGridRhoFastjetCentralCalo using the MattWIP ntuplizer formula "
        "max(0, caloTotal - rhoCentralCalo * pi * 0.4^2)."
    ),
    "trk_hitDrop_missingMiddleHits": (
        "For OSUNano inputs this maps to IsoTrack_missingMiddleHits."
    ),
    "trk_relativePFIso": (
        "For OSUNano inputs this maps first to IsoTrack_pfRelIso03_chg, matching "
        "the MattWIP ntuplizer charged-hadron DR03 relative isolation definition."
    ),
    "Electron_eta": (
        "Electron_eta is required for the electron-track veto. For strict MattWIP "
        "parity PCAS prefers RawElectron_eta from slimmedElectrons; otherwise it "
        "falls back to the central Electron table coordinates."
    ),
    "Electron_phi": (
        "Electron_phi is required for the electron-track veto. For strict MattWIP "
        "parity PCAS prefers RawElectron_phi from slimmedElectrons; otherwise it "
        "falls back to the central Electron table coordinates."
    ),
    "jet_isTightLepVeto": (
        "Required for strict MattWIP Pveto parity. PCAS prefers RawJet_isTightLepVeto "
        "from MiniAOD slimmedJets; if it is absent, PCAS falls back to Jet_isTightLepVeto "
        "or reconstructs it from central Jet energy-fraction and multiplicity branches."
    ),
}


@dataclass
class Count:
    value: float = 0.0
    variance: float = 0.0

    @property
    def error(self) -> float:
        return math.sqrt(max(self.variance, 0.0))

    def add_poisson(self, n: float) -> None:
        self.value += float(n)
        self.variance += float(n)

    def as_json(self) -> dict[str, float]:
        return {"value": self.value, "variance": self.variance, "error": self.error}


def normalize_layers(layer: str) -> list[str]:
    return list(LAYERS) if layer == "all" else [layer]


def branch_options(name: str) -> tuple[str, ...]:
    if name in BRANCH_ALIASES:
        return BRANCH_ALIASES[name]
    return (name,)


def has_exact_branch(arrays, name: str) -> bool:
    if name in arrays.fields:
        return True
    if "_" not in name:
        return False
    collection, field = name.split("_", 1)
    return collection in arrays.fields and field in arrays[collection].fields


def has_branch(arrays, name: str) -> bool:
    if any(has_exact_branch(arrays, option) for option in branch_options(name)):
        return True
    if name in COMPUTED_BRANCH_REQUIREMENTS:
        return all(has_branch(arrays, req) for req in COMPUTED_BRANCH_REQUIREMENTS[name])
    return False


def available_option(available: set[str], name: str) -> str | None:
    for option in branch_options(name):
        if option in available:
            return option
    return None


def available_has_branch(available: set[str], name: str) -> bool:
    if available_option(available, name) is not None:
        return True
    if name in COMPUTED_BRANCH_REQUIREMENTS:
        return all(available_has_branch(available, req) for req in COMPUTED_BRANCH_REQUIREMENTS[name])
    return False


def input_branches_for_available(available: set[str]) -> list[str]:
    needed = []
    for name in PVETO_BRANCHES:
        option = available_option(available, name)
        if option is not None:
            needed.append(option)
            continue
        if name in COMPUTED_BRANCH_REQUIREMENTS and all(
            available_has_branch(available, req) for req in COMPUTED_BRANCH_REQUIREMENTS[name]
        ):
            for req in COMPUTED_BRANCH_REQUIREMENTS[name]:
                req_option = available_option(available, req)
                needed.append(req_option if req_option is not None else req)
    for name in OPTIONAL_BRANCHES:
        option = available_option(available, name)
        if option is not None:
            needed.append(option)
    return sorted(set(needed))


def missing_required_for_available(available: set[str]) -> list[str]:
    return [name for name in PVETO_BRANCHES if not available_has_branch(available, name)]


def missing_branch_message(name: str) -> str:
    note = BRANCH_NOTES.get(name)
    if note:
        return f"Required branch {name} not found. {note}"
    return f"Required branch {name} not found in DLS/OSUNano Pveto input."


def exact_branch(arrays, name: str):
    if name in arrays.fields:
        return arrays[name]
    if "_" in name:
        collection, field = name.split("_", 1)
        if collection in arrays.fields:
            return arrays[collection][field]
    raise KeyError(name)


def branch(arrays, name: str):
    """Read a canonical DLS Pveto branch, with OSUNano aliases if needed."""
    if name == "trk_caloTotNoPU" and not has_exact_branch(arrays, name):
        if all(has_branch(arrays, req) for req in COMPUTED_BRANCH_REQUIREMENTS[name]):
            calo_total = branch(arrays, "trk_caloTotal")
            rho = branch(arrays, "Rho_fixedGridRhoFastjetCentralCalo")
            return np.maximum(0.0, calo_total - rho * np.pi * 0.4 * 0.4)

    if name == "jet_isTightLepVeto" and not any(
        has_exact_branch(arrays, option) for option in branch_options(name)
    ):
        if all(has_exact_branch(arrays, req) for req in COMPUTED_BRANCH_REQUIREMENTS[name]):
            abs_eta = np.abs(branch(arrays, "Jet_eta"))
            ne_hef = exact_branch(arrays, "Jet_neHEF")
            ne_em_ef = exact_branch(arrays, "Jet_neEmEF")
            n_const = exact_branch(arrays, "Jet_nConstituents")
            mu_ef = exact_branch(arrays, "Jet_muEF")
            ch_hef = exact_branch(arrays, "Jet_chHEF")
            ch_mult = exact_branch(arrays, "Jet_chMultiplicity")
            ch_em_ef = exact_branch(arrays, "Jet_chEmEF")
            ne_mult = exact_branch(arrays, "Jet_neMultiplicity")
            return (
                (
                    (abs_eta <= 2.6)
                    & (ne_hef < 0.99)
                    & (ne_em_ef < 0.9)
                    & (n_const > 1)
                    & (mu_ef < 0.8)
                    & (ch_hef > 0.01)
                    & (ch_mult > 0)
                    & (ch_em_ef < 0.8)
                )
                | (
                    (abs_eta > 2.6)
                    & (abs_eta <= 2.7)
                    & (ne_hef < 0.9)
                    & (ne_em_ef < 0.99)
                    & (mu_ef < 0.8)
                    & (ch_em_ef < 0.8)
                )
                | ((abs_eta > 2.7) & (abs_eta <= 3.0) & (ne_hef < 0.99))
                | ((abs_eta > 3.0) & (ne_em_ef < 0.4) & (ne_mult >= 2))
            )

    for option in branch_options(name):
        try:
            return exact_branch(arrays, option)
        except KeyError:
            continue

    raise KeyError(missing_branch_message(name))


def aligned_optional_branch(arrays, name: str, reference_name: str):
    """Return an optional branch only when its per-event length matches reference."""
    if not has_branch(arrays, name):
        return None

    value = branch(arrays, name)
    reference = branch(arrays, reference_name)
    try:
        value_counts = ak.num(value, axis=1)
        reference_counts = ak.num(reference, axis=1)
    except Exception:
        return None

    try:
        if bool(ak.all(value_counts == reference_counts)):
            return value
    except Exception:
        return None
    return None


def delta_phi(phi1, phi2):
    return np.arctan2(np.sin(phi1 - phi2), np.cos(phi1 - phi2))


def abs_lambda(eta):
    theta = 2.0 * np.arctan(np.exp(-eta))
    return np.abs((np.pi / 2.0) - theta)


def trans_mass(arrays, prefix: str):
    dphi = delta_phi(branch(arrays, f"{prefix}_phi"), branch(arrays, "metNoMu_phi"))
    return np.sqrt(
        2.0
        * branch(arrays, f"{prefix}_pt")
        * branch(arrays, "metNoMu_pt")
        * (1.0 - np.cos(dphi))
    )


def muon_trigger_match_mask(arrays):
    """Replicate MattWIP muon_isTrigMatched with NanoAOD TrigObj when needed."""
    saved_match = aligned_optional_branch(arrays, "muon_isTrigMatched", "Muon_pt")
    if saved_match is not None:
        return saved_match

    trig_fields = ("TrigObj_id", "TrigObj_filterBits", "TrigObj_eta", "TrigObj_phi")
    missing = [name for name in trig_fields if not has_branch(arrays, name)]
    if missing:
        raise KeyError(
            "Cannot reproduce MattWIP muon_isTrigMatched: input has no aligned "
            f"muon_isTrigMatched branch and is missing NanoAOD trigger object branches {missing}."
        )

    # OSUNano keeps the standard NanoAOD trigger-object table. For muons,
    # bit 3 is the documented single-muon (1mu) quality bit, which is the
    # closest stored equivalent to MattWIP's exact IsoMu24 HLT filter label.
    trig_mask = (np.abs(branch(arrays, "TrigObj_id")) == MUON_TRIGOBJ_ID) & (
        np.bitwise_and(
            branch(arrays, "TrigObj_filterBits"),
            1 << MUON_ISOMU24_STANDARD_NANOAOD_FILTER_BIT,
        ) != 0
    )
    muons = ak.zip({"eta": branch(arrays, "Muon_eta"), "phi": branch(arrays, "Muon_phi")})
    trig_objs = ak.zip({"eta": branch(arrays, "TrigObj_eta"), "phi": branch(arrays, "TrigObj_phi")})[
        trig_mask
    ]
    mu, obj = ak.unzip(ak.cartesian([muons, trig_objs], nested=True))
    dr = np.sqrt((mu.eta - obj.eta) ** 2 + delta_phi(mu.phi, obj.phi) ** 2)
    return ak.fill_none(ak.any(dr < MUON_TRIGGER_MATCHING_DR, axis=2), False)


def min_delta_r_mask(arrays, prefix: str, min_dr: float, obj_mask=None):
    tracks = ak.zip({"eta": branch(arrays, "trk_eta"), "phi": branch(arrays, "trk_phi")})
    objs = ak.zip(
        {"eta": branch(arrays, f"{prefix}_eta"), "phi": branch(arrays, f"{prefix}_phi")}
    )

    if obj_mask is not None:
        objs = objs[obj_mask]

    trk, obj = ak.unzip(ak.cartesian([tracks, objs], nested=True))
    dr = np.sqrt((trk.eta - obj.eta) ** 2 + delta_phi(trk.phi, obj.phi) ** 2)
    return ak.fill_none(ak.all(dr > min_dr, axis=2), True)


def any_pair_per_event(pair_mask):
    return ak.any(ak.flatten(pair_mask, axis=2), axis=1)


def layer_mask(arrays, layer: str):
    n_layers = branch(arrays, "trk_hp_trackerLayersWithMeasurement")

    if layer == "NLayers4":
        return n_layers == 4
    if layer == "NLayers5":
        return n_layers == 5
    if layer == "NLayers6plus":
        return n_layers >= 6
    if layer == "combinedBins":
        return n_layers >= 4

    raise ValueError(f"Unknown layer bin: {layer}")


def fiducial_eta_mask(arrays):
    trk_eta = branch(arrays, "trk_eta")
    return (
        ((np.abs(trk_eta) < 0.15) | (np.abs(trk_eta) > 0.35))
        & ((np.abs(trk_eta) < 1.42) | (np.abs(trk_eta) > 1.65))
        & ((np.abs(trk_eta) < 1.55) | (np.abs(trk_eta) > 1.85))
    )


def muon_tag_mask(arrays):
    mask = muon_trigger_match_mask(arrays)
    mask = mask & branch(arrays, "HLT_IsoMu24")
    mask = mask & (branch(arrays, "Muon_pt") > 26)
    mask = mask & (np.abs(branch(arrays, "Muon_eta")) < 2.1)
    mask = mask & branch(arrays, "Muon_tightId")
    mask = mask & (trans_mass(arrays, "Muon") < 40)
    return mask


def good_jet_mask(arrays):
    # Strict MattWIP parity: use the same clean-jet definition as the old
    # denominator, including the custom tight-lepton-veto jet ID.  OSUNano does
    # not save jet_isTightLepVeto directly, so branch() reconstructs it from
    # central Jet energy-fraction and multiplicity branches when needed.
    return (
        (branch(arrays, "Jet_pt") > 30)
        & (np.abs(branch(arrays, "Jet_eta")) < 4.5)
        & branch(arrays, "jet_isTightLepVeto")
    )


def probe_track_denominator_mask(arrays, layer: str):
    mask = (branch(arrays, "trk_pt") > 30) & branch(arrays, "HLT_IsoMu24")
    mask = mask & (np.abs(branch(arrays, "trk_eta")) < 2.1)
    mask = mask & fiducial_eta_mask(arrays)
    mask = mask & (
        (np.abs(branch(arrays, "trk_dz")) > 0.5)
        | (np.abs((np.pi / 2.0) - branch(arrays, "trk_theta")) > 1.0e-3)
    )
    mask = mask & (branch(arrays, "trk_hp_numberOfValidPixelHits") >= 4)
    mask = mask & (branch(arrays, "trk_missingInnerHits") == 0)
    mask = mask & (branch(arrays, "trk_hitDrop_missingMiddleHits") == 0)
    mask = mask & (branch(arrays, "trk_relativePFIso") < 0.05)
    mask = mask & (np.abs(branch(arrays, "trk_dxy")) < 0.02)
    mask = mask & (np.abs(branch(arrays, "trk_dz")) < 0.5)

    mask = mask & min_delta_r_mask(arrays, "Jet", 0.5, obj_mask=good_jet_mask(arrays))
    mask = mask & min_delta_r_mask(arrays, "Electron", 0.15)
    mask = mask & (branch(arrays, "trk_caloTotNoPU") < 10)
    mask = mask & layer_mask(arrays, layer)

    return mask


def build_muon_vectors(arrays, mask):
    return ak.zip(
        {
            "pt": branch(arrays, "Muon_pt")[mask],
            "eta": branch(arrays, "Muon_eta")[mask],
            "phi": branch(arrays, "Muon_phi")[mask],
            "mass": ak.ones_like(branch(arrays, "Muon_pt")[mask]) * MUON_MASS,
            "charge": branch(arrays, "Muon_charge")[mask],
        },
        with_name="Momentum4D",
    )


def build_track_vectors(arrays, mask):
    muon_veto = min_delta_r_mask(arrays, "Muon", 0.15)

    return ak.zip(
        {
            "pt": branch(arrays, "trk_pt")[mask],
            "eta": branch(arrays, "trk_eta")[mask],
            "phi": branch(arrays, "trk_phi")[mask],
            "mass": ak.ones_like(branch(arrays, "trk_pt")[mask]) * MUON_MASS,
            "charge": branch(arrays, "trk_charge")[mask],
            "missingOuterHits": branch(arrays, "trk_missingOuterHits")[mask],
            "passesMuonVeto": muon_veto[mask],
        },
        with_name="Momentum4D",
    )


def make_tp_cutflow(arrays, layer: str):
    cutflow = OrderedDict()
    event_mask = ak.ones_like(branch(arrays, "metNoMu_pt"), dtype=bool)

    def add(label: str, mask) -> None:
        nonlocal event_mask
        event_mask = event_mask & mask
        cutflow[label] = int(ak.sum(event_mask))

    add("event passes SingleMuon triggers", branch(arrays, "HLT_IsoMu24"))

    mu = muon_trigger_match_mask(arrays)
    mu = mu & (branch(arrays, "Muon_pt") > 26)
    add(">= 1 muons pT > 26 GeV", ak.any(mu, axis=1))
    mu = mu & (np.abs(branch(arrays, "Muon_eta")) < 2.1)
    add(">= 1 muons |eta| < 2.1", ak.any(mu, axis=1))
    mu = mu & branch(arrays, "Muon_tightId")
    add(">= 1 muons passing tight muon ID", ak.any(mu, axis=1))
    mu = mu & (trans_mass(arrays, "Muon") < 40)
    add(">= 1 muons MT(pTmiss, muon) < 40 GeV", ak.any(mu, axis=1))
    add("exactly one passing muon chosen randomly", ak.any(mu, axis=1))

    trk = branch(arrays, "trk_pt") > 30
    add(">= 1 tracks pT > 30 GeV", ak.any(trk, axis=1))
    trk = trk & (np.abs(branch(arrays, "trk_eta")) < 2.1)
    add(">= 1 tracks |eta| < 2.1", ak.any(trk, axis=1))
    trk_eta = branch(arrays, "trk_eta")
    trk = trk & ((np.abs(trk_eta) < 0.15) | (np.abs(trk_eta) > 0.35))
    add(">= 1 tracks |eta| < 0.15 OR |eta| > 0.35", ak.any(trk, axis=1))
    trk = trk & ((np.abs(trk_eta) < 1.42) | (np.abs(trk_eta) > 1.65))
    add(">= 1 tracks |eta| < 1.42 OR |eta| > 1.65", ak.any(trk, axis=1))
    trk = trk & ((np.abs(trk_eta) < 1.55) | (np.abs(trk_eta) > 1.85))
    add(">= 1 tracks |eta| < 1.55 OR |eta| > 1.85", ak.any(trk, axis=1))
    trk = trk & (
        (np.abs(branch(arrays, "trk_dz")) > 0.5)
        | (np.abs((np.pi / 2.0) - branch(arrays, "trk_theta")) > 1.0e-3)
    )
    add(">= 1 tracks |dz| > 0.5 cm OR |lambda| > 1e-3", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_hp_numberOfValidPixelHits") >= 4)
    add(">= 1 tracks number of pixel hits >= 4", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_missingInnerHits") == 0)
    add(">= 1 tracks missing inner hits = 0", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_hitDrop_missingMiddleHits") == 0)
    add(">= 1 tracks missing middle hits = 0", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_relativePFIso") < 0.05)
    add(">= 1 tracks rel. PF-based iso. < 0.05", ak.any(trk, axis=1))
    trk = trk & (np.abs(branch(arrays, "trk_dxy")) < 0.02)
    add(">= 1 tracks |dxy| < 0.02 cm", ak.any(trk, axis=1))
    trk = trk & (np.abs(branch(arrays, "trk_dz")) < 0.5)
    add(">= 1 tracks |dz| < 0.5 cm", ak.any(trk, axis=1))
    trk = trk & min_delta_r_mask(arrays, "Jet", 0.5, obj_mask=good_jet_mask(arrays))
    add(">= 1 track-jet pairs DeltaRtrack,jet > 0.5", ak.any(trk, axis=1))

    muons = build_muon_vectors(arrays, mu)
    tracks_pre_veto = build_track_vectors(arrays, trk)
    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks_pre_veto, muons], nested=True))
    mass = (trk_obj + mu_obj).mass
    add(">= 1 track-muon pairs Mtrack,muon > 10 GeV", any_pair_per_event(mass > 10))

    trk = trk & min_delta_r_mask(arrays, "Electron", 0.15)
    add(">= 1 tracks min DeltaRtrack,electron > 0.15", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_caloTotNoPU") < 10)
    add(">= 1 tracks Ecalo < 10 GeV", ak.any(trk, axis=1))
    add("exactly one passing track chosen randomly", ak.any(trk, axis=1))

    trk = trk & layer_mask(arrays, layer)
    muons = build_muon_vectors(arrays, mu)
    tracks = build_track_vectors(arrays, trk)
    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks, muons], nested=True))
    mass = (trk_obj + mu_obj).mass

    z_window = (mass > Z_MASS - 10) & (mass < Z_MASS + 10)
    add("= 1 track-muon pairs |Mtrack,muon - MZ| < 10 GeV", any_pair_per_event(z_window))
    os_pair = z_window & (trk_obj.charge * mu_obj.charge < 0)
    add("= 1 track-muon pairs qtrack * qmuon < 0", any_pair_per_event(os_pair))
    add(f">= 1 track nlayers >= 4 ({layer})", any_pair_per_event(os_pair))

    return cutflow


def count_pveto_pairs(arrays, layer: str) -> dict[str, float]:
    mu = muon_tag_mask(arrays)
    trk = probe_track_denominator_mask(arrays, layer)

    muons = build_muon_vectors(arrays, mu)
    tracks = build_track_vectors(arrays, trk)
    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks, muons], nested=True))

    mass = (trk_obj + mu_obj).mass
    z_window = (mass > 10.0) & (mass > Z_MASS - 10) & (mass < Z_MASS + 10)
    os_pair = trk_obj.charge * mu_obj.charge < 0
    ss_pair = trk_obj.charge * mu_obj.charge > 0

    passes_veto = trk_obj.passesMuonVeto & (trk_obj.missingOuterHits >= 3)

    return {
        "p_veto_den_os": float(ak.sum(z_window & os_pair)),
        "p_veto_den_ss": float(ak.sum(z_window & ss_pair)),
        "p_veto_num_os": float(ak.sum(z_window & os_pair & passes_veto)),
        "p_veto_num_ss": float(ak.sum(z_window & ss_pair & passes_veto)),
    }


def empty_counts() -> dict[str, Count]:
    return {
        "p_veto_num_os": Count(),
        "p_veto_num_ss": Count(),
        "p_veto_den_os": Count(),
        "p_veto_den_ss": Count(),
    }


def merge_layer_result(target: dict, source: dict) -> None:
    for name, value in source["cutflow"].items():
        target["cutflow"][name] = target["cutflow"].get(name, 0) + int(value)
    for name, value in source["counts"].items():
        target["counts"][name].add_poisson(value)


def process_arrays(arrays, layer: str) -> dict:
    return {
        "cutflow": make_tp_cutflow(arrays, layer),
        "counts": count_pveto_pairs(arrays, layer),
    }


def make_payload(input_files: Iterable[str], tree: str, layer_results: dict) -> dict:
    payload = {"input_files": list(input_files), "tree": tree, "layers": {}}
    for layer, result in layer_results.items():
        payload["layers"][layer] = {
            "cutflow": dict(result["cutflow"]),
            "counts": {name: count.as_json() for name, count in result["counts"].items()},
        }
    return payload
