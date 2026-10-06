#!/bin/bash
# Activate the environment for building/running the local 1pt E3SM case.
#
# Usage (must be SOURCED, not executed):
#   source e3sm_tools/scripts/activate_e3sm.sh
#
# Roles:
#   python (arm64, /opt/anaconda3) : python for CIME scripts (setup/build/run)
#   e3sm-build   : native arm64 netcdf-fortran/hdf5/cmake AND the conda-forge
#                  GNU 16 compilers used to build the model
#   (MacPorts gcc-mp-14 is NOT used: broken against the macOS 26 SDK)
#
# IMPORTANT: do NOT run CIME with the e3sm-unified env's python. e3sm-unified
# is an osx-64 (x86_64) env, so its python runs under Rosetta and Rosetta
# propagates to all spawned children: cmake/autoconf then see `uname -m` =
# x86_64, so CMake sets CMAKE_SYSTEM_PROCESSOR=x86_64 -> gnu.cmake appends
# -mcmodel=medium, which arm64 gcc rejects, and autoconf scripts detect a
# bogus x86_64 host triplet. Everything in the build tree must be arm64.

# refuse to execute (must be sourced for PATH/exports to affect the shell)
if [ "$0" = "${BASH_SOURCE[0]:-}" ] && [ -n "$BASH_VERSION$ZSH_VERSION" ]; then
  echo "ERROR: source this file instead of executing it:" >&2
  echo "  source $0" >&2
  return 1 2>/dev/null || exit 1
fi

CONDA_BASE="$HOME/miniforge3"

if [ ! -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
  echo "ERROR: conda not found at $CONDA_BASE" >&2
  return 1 2>/dev/null || exit 1
fi

# `conda init` does NOT enable activate in the current shell; sourcing the
# conda.sh hook is what makes `conda activate` work here.
source "$CONDA_BASE/etc/profile.d/conda.sh"

# leave any active conda env so its binaries don't shadow native ones
if [ -n "${CONDA_DEFAULT_ENV:-}" ] && [ "$CONDA_DEFAULT_ENV" != "base" ]; then
  conda deactivate
fi

if ! conda env list | grep -q "^e3sm-build "; then
  echo "ERROR: conda env 'e3sm-build' not found (run ./recreate_1pt_case.sh once to create it)" >&2
  return 1 2>/dev/null || exit 1
fi

# native arm64 python for CIME scripts (needs pyyaml + lxml)
NATIVE_PYTHON="/opt/anaconda3/bin/python"
if [ ! -x "$NATIVE_PYTHON" ]; then
  echo "ERROR: native arm64 python not found at $NATIVE_PYTHON" >&2
  return 1 2>/dev/null || exit 1
fi
if ! "$NATIVE_PYTHON" -c "import yaml, lxml" 2>/dev/null; then
  echo "ERROR: $NATIVE_PYTHON lacks pyyaml/lxml required by CIME" >&2
  return 1 2>/dev/null || exit 1
fi

# shim dir exposing only the native python3/python (avoids shadowing anything
# else from /opt/anaconda3/bin)
SHIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.native_bin"
mkdir -p "$SHIM_DIR"
ln -sf "$NATIVE_PYTHON" "$SHIM_DIR/python3"
ln -sf "$NATIVE_PYTHON" "$SHIM_DIR/python"

# arm64 build libraries for the model build
export NETCDF_C_PATH="$CONDA_BASE/envs/e3sm-build"
export NETCDF_FORTRAN_PATH="$CONDA_BASE/envs/e3sm-build"

# PATH order: shim python3, e3sm-build's arm64 cmake, Homebrew (mpi wrappers,
# mpirun), then system tools
export PATH="$SHIM_DIR:$CONDA_BASE/envs/e3sm-build/bin:$E3SM_TOOLCHAIN:$PATH"

# Scrub any osx-64 (x86_64) cross-toolchain vars a conda env activation (e.g.
# e3sm-unified) may have exported, and pin the arm64 toolchain: Homebrew Open
# MPI wrappers for the parallel build (mpicc->Apple clang, mpif90->gfortran
# 16). Mirrors cmake_macros/mac_gnu.cmake.
unset CFLAGS CXXFLAGS FFLAGS FCFLAGS CPPFLAGS LDFLAGS HOST
unset host_alias build_alias CC_FOR_BUILD CXX_FOR_BUILD CPP_FOR_BUILD
E3SM_TOOLCHAIN="/opt/homebrew/bin"
export CC="$E3SM_TOOLCHAIN/mpicc" CXX="$E3SM_TOOLCHAIN/mpicxx" FC="$E3SM_TOOLCHAIN/mpif90"
export F77="$E3SM_TOOLCHAIN/mpif90" F90="$E3SM_TOOLCHAIN/mpif90"

# cmake 4.x (e3sm-build) dropped compatibility with cmake_minimum_required < 3.5,
# which old bundled code (scorpio clib) still declares.
export CMAKE_POLICY_VERSION_MINIMUM=3.5

# MOAB (driver-moab interface) and tempest-remap from conda-forge, osx-arm64
export MOAB_DIR="$CONDA_BASE/envs/e3sm-build"
export TEMPEST_REMAP_DIR="$CONDA_BASE/envs/e3sm-build"
export CMAKE_PREFIX_PATH="$CONDA_BASE/envs/e3sm-build:${CMAKE_PREFIX_PATH:-}"

# MacPorts gcc-mp-14 needs an explicit SDK to link against libSystem
if [ -z "${SDKROOT:-}" ] || [ ! -d "$SDKROOT" ]; then
  export SDKROOT="$(xcrun --show-sdk-path 2>/dev/null)"
fi

# sanity checks
if [ "$(uname -m)" != "arm64" ]; then
  echo "WARNING: uname -m is '$(uname -m)', expected arm64" >&2
fi
if [ ! -f "$NETCDF_C_PATH/lib/libnetcdff.dylib" ]; then
  echo "WARNING: $NETCDF_C_PATH has no arm64 libnetcdff (env may have been created as osx-64)" >&2
fi
case "$(command -v cmake)" in
  "$CONDA_BASE/envs/e3sm-build/bin/cmake") : ;;
  *) echo "WARNING: cmake resolves to $(command -v cmake), expected arm64 one from e3sm-build" >&2 ;;
esac
PY_MACH="$("$SHIM_DIR/python3" -c 'import platform; print(platform.machine())' 2>/dev/null)"
if [ "$PY_MACH" != "arm64" ]; then
  echo "WARNING: CIME python reports machine=$PY_MACH, expected arm64 (Rosetta would break cmake/autoconf detection)" >&2
fi

echo "e3sm env ready:"
echo "  python : $(command -v python3) (arm64: $([ "$PY_MACH" = arm64 ] && echo yes || echo NO))"
echo "  cmake  : $(command -v cmake)"
echo "  netcdf : $NETCDF_C_PATH"