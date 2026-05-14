#!/bin/bash
# Create a CMSSW tarball for condor jobs and upload it to EOS.
# Run this on the LPC after rebuilding CMSSW.
#
# Usage: bash package_cmssw_tarball.sh

set -e

CMSSW_VERSION=CMSSW_15_0_10
CMSSW_BASE_DIR=/uscms_data/d3/lnestor/DisplacedLeptons_CMSSW
EOS_PATH="root://cmseos.fnal.gov//store/user/lnestor/${CMSSW_VERSION}.tgz"
TARBALL="${CMSSW_VERSION}.tgz"

echo "Creating tarball ${TARBALL}..."
cd "$CMSSW_BASE_DIR"
tar --exclude="${CMSSW_VERSION}/tmp" \
    --exclude="${CMSSW_VERSION}/src/.git" \
    -czf "$TARBALL" "$CMSSW_VERSION/"
echo "  $(du -sh "$TARBALL" | cut -f1) written"

echo "Uploading to EOS..."
xrdcp -f "$TARBALL" "$EOS_PATH"
echo "  Uploaded to ${EOS_PATH}"

rm "$TARBALL"
echo "Done."
