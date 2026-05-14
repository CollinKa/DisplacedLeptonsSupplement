#!/bin/bash
# Condor job wrapper for verify_custom_nanoaod.py.
#
# Arguments (set by condor submit file):
#   $1  custom file LFN  (/store/user/...)
#   $2  central NanoAOD file LFNs, comma-separated
#   $3  central MiniAOD file LFNs, comma-separated, or "-" if none
#   $4  output JSON filename (transferred back to results dir)
#
# verify_custom_nanoaod.py is transferred to the job working directory by condor.

set -e

echo "Starting job on $(date)"
echo "Running on: $(uname -a)"
echo "System software: $(cat /etc/redhat-release)"

CUSTOM_LFN=$1
CENTRAL_CSV=$2
MINIAOD_CSV=$3
OUTPUT_JSON=$4

# ---------------------------------------------------------------------------
# Set up CMSSW.  We use the pre-compiled tarball so the custom DisplacedMuon
# plugins are available for cmsRun (needed for MiniAOD extraction).
#
# Before submitting jobs, create the tarball on the LPC with:
#   cd $CMSSW_BASE/..
#   tar --exclude="tmp" --exclude=".git" \
#       -czf CMSSW_15_0_10.tgz CMSSW_15_0_10
#   xrdcp CMSSW_15_0_10.tgz root://cmseos.fnal.gov//store/user/lnestor/
# ---------------------------------------------------------------------------
CMSSW_VERSION=CMSSW_15_0_10
CMSSW_TARBALL="root://cmseos.fnal.gov//store/user/lnestor/${CMSSW_VERSION}.tgz"

echo "Fetching CMSSW tarball..."
xrdcp -s "$CMSSW_TARBALL" .

source /cvmfs/cms.cern.ch/cmsset_default.sh
tar -xf "${CMSSW_VERSION}.tgz"
rm "${CMSSW_VERSION}.tgz"
cd "${CMSSW_VERSION}/src/"
scramv1 b ProjectRename
eval "$(scramv1 runtime -sh)"
echo "$CMSSW_BASE is the CMSSW we have on the local worker node"

# Save the CMSSW Python environment before LCG overwrites PATH/PYTHONPATH/PYTHONHOME.
# _cmsrun_env() in verify_custom_nanoaod.py uses these to give cmsRun a clean env.
# PYTHONHOME is captured explicitly because scramv1 runtime doesn't set it — Python
# would otherwise fall back to its hardcoded build-time prefix which doesn't exist
# on the worker node.
export CMSSW_SAVED_PATH="${PATH}"
export CMSSW_SAVED_PYTHONPATH="${PYTHONPATH:-}"
export CMSSW_SAVED_PYTHONHOME="$(python3 -c 'import sys; print(sys.prefix)')"

cd "${_CONDOR_SCRATCH_DIR}"

# ---------------------------------------------------------------------------
# Set up Python environment (provides uproot, awkward, numpy).
# ---------------------------------------------------------------------------
source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-el9-gcc13-opt/setup.sh

# extract_cfg.py lives inside the CMSSW source tree we just unpacked.
EXTRACT_CFG="$CMSSW_BASE/src/DisplacedLeptonsSupplement/CustomNanoAOD/python/extract_cfg.py"

# Convert comma-separated LFNs to arrays.
IFS=',' read -ra CENTRAL_PARTS <<< "$CENTRAL_CSV"

CMD=(python verify_custom_nanoaod.py "$CUSTOM_LFN" batch
    --nanoaod-filenames "${CENTRAL_PARTS[@]}"
    --extract-cfg "$EXTRACT_CFG"
    --output-json "$OUTPUT_JSON")

if [ "$MINIAOD_CSV" != "-" ]; then
    IFS=',' read -ra MINIAOD_PARTS <<< "$MINIAOD_CSV"
    CMD+=(--miniaod-filenames "${MINIAOD_PARTS[@]}")
fi

"${CMD[@]}"
