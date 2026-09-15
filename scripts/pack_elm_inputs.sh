#!/bin/bash
# Run from the inputdata directory:
#   bash /path/to/pack_elm_inputs.sh [output.tar]
set -euo pipefail

archive="${1:-elm_ancillary_inputs.tar}"
# Prefix relative paths so tar cannot interpret a leading dash as an option.
case "$archive" in
  /*) ;;
  *) archive="./$archive" ;;
esac

files=(
  "lnd/clm2/paramdata/clm_params_c251006.nc"
  "lnd/clm2/paramdata/CNP_parameters_c180529.nc"
  "lnd/clm2/snicardata/snicar_optics_5bnd_mam_c160322.nc"
  "lnd/clm2/snicardata/snicar_drdt_bst_fit_60_c070416.nc"
  "lnd/clm2/ndepdata/fndep_elm_cbgc_exp_simyr1849-2101_1.9x2.5_ssp245_c240903.nc"
  "lnd/clm2/pdepdata/fpdep_clm_hist_simyr2000_1.9x2.5_c150929.nc"
  "lnd/clm2/firedata/elmforc.Li_20181205_mod_hist_SSP2_CMIP6_hdm_0.5x0.5_AVHRR_simyr1850-2100_c240906.nc"
  "atm/datm7/NASA_LIS/clmforc.Li_2012_climo1995-2011.T62.lnfm_Total_c140423.nc"
  "atm/cam/chem/trop_mozart_aero/aero/aerosoldep_monthly_1850_mean_1.9x2.5_c090421.nc"
  "atm/datm7/topo_forcing/topodata_0.9x1.25_USGS_070110_stream_c151201.nc"
)

missing=0
for file in "${files[@]}"; do
  if [[ ! -f "$file" || ! -r "$file" ]]; then
    printf 'Missing or unreadable: %s\n' "$file" >&2
    missing=1
  fi
done
if [[ "$missing" -ne 0 ]]; then
  printf 'Run from inputdata with all ten files available. No archive created.\n' >&2
  exit 1
fi

if [[ -e "$archive" || -L "$archive" ]]; then
  printf 'Output already exists; choose another filename: %s\n' "$archive" >&2
  exit 1
fi

# Dereference symlinks to store the actual data, including on shared HPC storage.
tar -chvf "$archive" "${files[@]}"
printf 'Created %s containing %s data files.\n' "$archive" "${#files[@]}"
