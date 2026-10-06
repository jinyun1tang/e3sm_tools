#!/bin/bash
#SBATCH --job-name=landuse_rebal
#SBATCH --account=e3sm
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH --time=04:00:00
#SBATCH --output=landuse_rebal-%j.out
#SBATCH --error=landuse_rebal-%j.err

# Submit from e3sm_tools/scripts on Chrysalis:
#   sbatch run_landuse_surf_data_checksum_chrysalis.slurm
# Alternatively pass the absolute Python script path as the first argument.
# Output NetCDF and logs are written in the submission directory.
set -eo pipefail

source /lcrc/soft/climate/e3sm-unified/load_latest_e3sm_unified_chrysalis.sh
set -u

cd "${SLURM_SUBMIT_DIR:?Submit this script with sbatch}"
CHECKSUM_SCRIPT="${1:-$SLURM_SUBMIT_DIR/landuse_surf_data_checksum.py}"
if [[ ! -r "$CHECKSUM_SCRIPT" ]]; then
    echo "Cannot read Python script: $CHECKSUM_SCRIPT" >&2
    exit 1
fi

# Keep numerical-library threads from oversubscribing Dask's worker threads.
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1

echo "Started $(date) on $(hostname)"
echo "Script: $CHECKSUM_SCRIPT"
echo "Output directory: $PWD"

# Run one Python process; this script is not an MPI program.
python - "$CHECKSUM_SCRIPT" <<'PY'
import os
import runpy
import sys

import dask
import netCDF4
import numpy
import xarray

script = sys.argv[1]
sys.argv = [script]
with dask.config.set(scheduler="threads",
                     num_workers=int(os.environ["SLURM_CPUS_PER_TASK"])):
    runpy.run_path(script, run_name="__main__")
PY

echo "Finished $(date)"
