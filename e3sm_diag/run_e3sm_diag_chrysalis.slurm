#!/bin/bash
#SBATCH --job-name=e3sm_diag
#SBATCH --account=e3sm
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --exclusive
#SBATCH --time=01:40:00
#SBATCH --output=e3sm_diag-%j.out
#SBATCH --error=e3sm_diag-%j.err
#SBATCH --mail-user=jinyuntang@lbl.gov
#SBATCH --mail-type=END,FAIL

# Run the ELM e3sm_diags workflow from README on Chrysalis:
#   1. create_climo_chrysalis.py      -> ncclimo seasonal/annual climatologies
#   2. run_e3sm_diags_hist_chrysalis.py -d diags_v2_CBGC.cfg -> lat_lon plots
# Case, years, run and output directories are set inside those two scripts.
#
# Submit from e3sm_tools/e3sm_diag on Chrysalis:
#   sbatch run_e3sm_diag_chrysalis.slurm              # climo + diags
#   sbatch run_e3sm_diag_chrysalis.slurm --skip-climo # diags only, reuse climo/
# It can also run inside an interactive session (srun -N 1 -t 100 --pty bash):
#   bash run_e3sm_diag_chrysalis.slurm
set -eo pipefail

SKIP_CLIMO=false
for arg in "$@"; do
    case "$arg" in
        --skip-climo) SKIP_CLIMO=true ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

source /lcrc/soft/climate/e3sm-unified/load_latest_e3sm_unified_chrysalis.sh
set -u

# sbatch runs a copy of this script, so locate the inputs from the submit dir.
DIAG_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$DIAG_DIR"
for f in create_climo_chrysalis.py run_e3sm_diags_hist_chrysalis.py diags_v2_CBGC.cfg; do
    if [[ ! -r "$f" ]]; then
        echo "Cannot read $DIAG_DIR/$f; run from e3sm_tools/e3sm_diag" >&2
        exit 1
    fi
done

export PYTHONUNBUFFERED=1

echo "Started $(date) on $(hostname)"
echo "Working directory: $PWD"

if [[ "$SKIP_CLIMO" == true ]]; then
    echo "Skipping climatology step (--skip-climo)"
else
    echo "=== Step 1: climatologies (ncclimo) ==="
    python create_climo_chrysalis.py
fi

echo "=== Step 2: e3sm_diags ==="
python run_e3sm_diags_hist_chrysalis.py -d diags_v2_CBGC.cfg

echo "Finished $(date)"
