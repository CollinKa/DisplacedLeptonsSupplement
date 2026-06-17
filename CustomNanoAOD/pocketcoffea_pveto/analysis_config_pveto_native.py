from __future__ import annotations

import os
from pathlib import Path
import sys

from pocket_coffea.parameters.defaults import get_default_parameters
from pocket_coffea.utils.configurator import Configurator, passthrough

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from dls_pveto_core import LAYERS
from dls_pveto_cuts import get_pveto_denominator_cut
from dls_pveto_native_workflow import (
    DisappTrksPvetoNativeWorkflow,
)

dataset_json = os.environ.get(
    "DISAPPTRKS_PVETO_DATASET_JSON",
    str(HERE / "datasets" / "dls_trimmed_nanoaod_smoke.json"),
)

cfg = Configurator(
    workflow=DisappTrksPvetoNativeWorkflow,
    parameters=get_default_parameters(),
    datasets={
        "jsons": [dataset_json],
        "filter": {
            "samples": ["DATA_Muon"],
            "year": ["2022"],
        },
    },
    skim=[passthrough],
    preselections=[passthrough],
    categories={
        "inclusive": [passthrough],
        **{
            f"pveto_denominator_{layer}": [get_pveto_denominator_cut(layer)]
            for layer in LAYERS
        },
    },
    weights={"common": {"inclusive": [], "bycategory": {}}},
    variations={
        "weights": {"common": {"inclusive": [], "bycategory": {}}},
        "shape": {"common": {"inclusive": [], "bycategory": {}}},
    },
    variables={},
    weights_classes=[],
    calibrators=[],
    columns={},
    workflow_options={"layers": LAYERS},
    do_postprocessing=False,
)
