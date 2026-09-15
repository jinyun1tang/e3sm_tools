#!/bin/bash
# Create the input-data directory layout for cases/1pt_case_0910.
# Usage: bash create_inputdata_dirs.sh [alternative_inputdata_root]
# Safe to rerun: existing directories and files are preserved.
set -euo pipefail

inputdata_root="${1:-/Users/jinyuntang/work/github/e3sm_new/inputdata}"
gswp3="atm/datm7/atm_forcing.datm7.GSWP3.0.5d.v1.c170516"

directories=(
  "$gswp3/Solar"
  "$gswp3/Precip"
  "$gswp3/TPHWL"
  "atm/datm7/NASA_LIS"
  "atm/datm7/topo_forcing"
  "atm/cam/chem/trop_mozart_aero/aero"
  "lnd/clm2/paramdata"
  "lnd/clm2/snicardata"
  "lnd/clm2/ndepdata"
  "lnd/clm2/pdepdata"
  "lnd/clm2/firedata"
  "lnd/clm2/surfdata_map"
  "rof/mosart"
)

for directory in "${directories[@]}"; do
  mkdir -p "$inputdata_root/$directory"
done

printf 'Input-data directories ready under: %s\n' "$inputdata_root"
printf 'No data files were downloaded or modified.\n'
