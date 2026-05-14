#!/bin/bash
# Condor job wrapper for verify_nano.py.
#
# Arguments (set by condor submit file):
#   $1  custom file LFN  (/store/user/...)
#   $2  central file LFNs, comma-separated (/store/mc/.../f1.root,...)
#   $3  output JSON path
#
# verify_nano.py is transferred to the job working directory by condor.

set -e

CUSTOM_LFN=$1
CENTRAL_CSV=$2
OUTPUT_JSON=$3

# ---------------------------------------------------------------------------
# Set up Python environment.
# Adjust this to match your setup — the environment must provide uproot,
# awkward, and numpy. Example using an LCG release:
#
#   source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-el9-gcc13-opt/setup.sh
#
# Or activate a conda/micromamba environment:
#
#   source /path/to/micromamba/etc/profile.d/micromamba.sh
#   micromamba activate my-env
# ---------------------------------------------------------------------------
source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-el9-gcc13-opt/setup.sh

# Convert comma-separated central LFNs to space-separated arguments
CENTRAL_ARGS=$(echo "$CENTRAL_CSV" | tr ',' ' ')

python verify_nano.py "$CUSTOM_LFN" \
    --eos \
    --central-files $CENTRAL_ARGS \
    --output-json "$OUTPUT_JSON"
