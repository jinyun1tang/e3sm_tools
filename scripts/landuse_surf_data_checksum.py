import numpy as np
import xarray as xr
import sys
import warnings
warnings.filterwarnings("ignore")

fpath = '/lcrc/group/e3sm/data/inputdata/lnd/clm2/surfdata_map/'
fname = 'landuse.timeseries_r025_hist_simyr1850-2015_c260808_50pfts.nc'

#read data
with xr.open_dataset(fpath + fname, chunks={'time': 1}) as ds:
    ds_new = ds.copy(deep=True)

# ---------------------------------------------------------
# Fill corrupt trailing years with the last valid year
# ---------------------------------------------------------
# In the c260808 source the last 9 slices (2007-2015) were never written:
# time = 0 and every field holds garbage (~1e-315, negative, NaN). ELM picks
# slices by YEAR and treats cur_year >= YEAR(last) as "past the end", so if
# YEAR(last) is 0 too it reads the garbage slice from 1850 on. Replace each slice
# whose time is not its expected year with the last valid slice before it,
# and set time/YEAR to the expected years.
FIRST_YEAR, LAST_YEAR = 1850, 2015
expected_years = np.arange(FIRST_YEAR, LAST_YEAR + 1)
if ds_new.sizes['time'] != expected_years.size:
    sys.exit(f"ERROR: expected {expected_years.size} time slices "
             f"({FIRST_YEAR}-{LAST_YEAR}), found {ds_new.sizes['time']}")

valid = ds_new['time'].values == expected_years
if not valid[0]:
    sys.exit(f"ERROR: first time slice is {ds_new['time'].values[0]}, expected {FIRST_YEAR}")
src_idx = np.maximum.accumulate(np.where(valid, np.arange(valid.size), 0))
if not valid.all():
    filled = expected_years[~valid]
    print(f'Filling corrupt years {filled.tolist()} with copies of '
          f'{sorted(set(expected_years[src_idx[~valid]].tolist()))}')
    time_attrs = ds_new['time'].attrs
    time_encoding = ds_new['time'].encoding
    ds_new = ds_new.isel(time=src_idx)
    ds_new = ds_new.assign_coords(time=('time', expected_years.astype(ds_new['time'].dtype)))
    ds_new['time'].attrs, ds_new['time'].encoding = time_attrs, time_encoding
    if 'YEAR' in ds_new:
        ds_new['YEAR'] = ds_new['YEAR'].copy(data=expected_years.astype(ds_new['YEAR'].dtype))
    # Record that these years are not real data.
    ds_new.attrs['corrupt_years_filled'] = (
        f'Years {filled.min()}-{filled.max()} ({filled.size} slices) were corrupt in {fname} '
        f'and are copies of year {expected_years[src_idx[~valid]].min()}; they contain no '
        f'land-use change after that year.')

# ---------------------------------------------------------
# 1850 Baseline Landuse Sum Rebalancing
# ---------------------------------------------------------
# Extract the 1850 crop value as a static 2D slice (lsmlat, lsmlon)
pct_crop_1850 = ds_new['PCT_CROP'].sel(time=1850).drop_vars('time', errors='ignore')
pct_urban_sum = ds_new['PCT_URBAN'].sum(dim='numurbl')

# Everything in this calculation is strictly 2D spatial now (no time dimension!)
suma = (ds_new['PCT_LAKE'] + ds_new['PCT_WETLAND'] + pct_urban_sum +
        ds_new['PCT_GLACIER'] + ds_new['PCT_NATVEG'] + pct_crop_1850)

# Cells where all landunits are 0 (or NaN) cannot be rescaled: 100/0 = inf and
# 0*inf = NaN would poison every PCT_* field there, so leave them unchanged.
deviation_mask = (suma > 0.0) & (abs(suma - 100.0) > (2.0 * sys.float_info.epsilon))
scale = 100.0 / xr.where(suma > 0.0, suma, 1.0)

# Update 1850 slice of PCT_CROP safely without altering other years
adjusted_crop_1850 = xr.where(deviation_mask, pct_crop_1850 * scale, pct_crop_1850)
ds_new['PCT_CROP'].loc[dict(time=1850)] = adjusted_crop_1850

# Update purely static 2D/3D variables (Scale is 2D, keeping dimensions clean!)
ds_new['PCT_NATVEG']  = xr.where(deviation_mask, ds_new['PCT_NATVEG'] * scale, ds_new['PCT_NATVEG'])
ds_new['PCT_WETLAND'] = xr.where(deviation_mask, ds_new['PCT_WETLAND'] * scale, ds_new['PCT_WETLAND'])
ds_new['PCT_LAKE']    = xr.where(deviation_mask, ds_new['PCT_LAKE'] * scale, ds_new['PCT_LAKE'])
ds_new['PCT_GLACIER'] = xr.where(deviation_mask, ds_new['PCT_GLACIER'] * scale, ds_new['PCT_GLACIER'])

# Because PCT_URBAN has (numurbl, lsmlat, lsmlon), multiplying by a 2D scale
# preserves its dimensions perfectly without expanding it to 4D time space!
ds_new['PCT_URBAN']   = xr.where(deviation_mask, ds_new['PCT_URBAN'] * scale, ds_new['PCT_URBAN'])

# ---------------------------------------------------------
# Repair bad PCT_NAT_PFT columns (see check_pct_nat_pft.py)
# ---------------------------------------------------------
# ELM aborts with "sum of PCT_NAT_PFT not 1.0" when
# abs(sum(PCT_NAT_PFT/100 over natpft) - 1) > 1e-14, i.e. 1e-12 in percent.
# Bad columns are NaN, all-zero ("no data" fill), negative, or off from 100.
# Good columns are left bit-identical; bad ones are repaired as follows:
#   nan/neg : NaN and negative values -> 0, then treated like the cases below
#   zero    : 100% bare ground (natpft 0), as mksurfdata writes at no-data points
#   off     : renormalized to 100, with the rounding residual put on the
#             largest PFT so the sum passes ELM's 1e-14 check
PCT_NAT_PFT_TOL = 1e-12
PCT_NAT_PFT_NODATA = 1e-6   # percent

def fix_pct_nat_pft(arr):
    """arr: PCT_NAT_PFT with natpft as the last axis."""
    has_nan = np.isnan(arr).any(axis=-1)
    has_neg = (arr < 0).any(axis=-1)
    s_raw = np.nansum(arr, axis=-1)
    bad = has_nan | has_neg | (np.abs(s_raw - 100.0) > PCT_NAT_PFT_TOL)
    if not bad.any():
        return arr

    # NaN/inf -> 0. Sums below PCT_NAT_PFT_NODATA (e.g. ~1e-315 garbage) count as
    # no data: rescaling them by 100/s would overflow to inf and give 0*inf = NaN.
    clean = np.clip(np.nan_to_num(arr.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0),
                    0.0, None)
    s = clean.sum(axis=-1)
    nodata = s < PCT_NAT_PFT_NODATA
    fixed = clean * (100.0 / np.where(nodata, 1.0, s))[..., None]

    # absorb the rounding residual into the largest PFT
    k = np.argmax(fixed, axis=-1)[..., None]
    others = fixed.sum(axis=-1, keepdims=True) - np.take_along_axis(fixed, k, axis=-1)
    np.put_along_axis(fixed, k, 100.0 - others, axis=-1)

    fixed[nodata] = 0.0
    fixed[nodata, 0] = 100.0
    return np.where(bad[..., None], fixed, arr).astype(arr.dtype)

ds_new['PCT_NAT_PFT'] = xr.apply_ufunc(
    fix_pct_nat_pft, ds_new['PCT_NAT_PFT'],
    input_core_dims=[['natpft']], output_core_dims=[['natpft']],
    dask='parallelized', output_dtypes=[ds_new['PCT_NAT_PFT'].dtype],
    keep_attrs=True)

# ---------------------------------------------------------
# Restore original dimension order and save output
# ---------------------------------------------------------
# xarray can silently reorder dimensions during operations (e.g. cft moves to last).
# Restore each variable to match the input file's dimension order before writing,
# otherwise ELM will read data in the wrong order without any error.
with xr.open_dataset(fpath + fname) as ds_orig:
    # Preserve source variables (including coordinates) not supplied by ds_new.
    # Keep any existing ds_new variables so rebalanced values are not overwritten.
    for var in ds_orig.variables:
        if var not in ds_new.variables:
            ds_new[var] = ds_orig[var].copy(deep=True)

    for var in ds_new.data_vars:
        if var in ds_orig and ds_new[var].dims != ds_orig[var].dims:
            print(f'Restoring dim order for {var}: {ds_new[var].dims} → {ds_orig[var].dims}')
            ds_new[var] = ds_new[var].transpose(*ds_orig[var].dims)

# Write lazy arrays directly; xarray applies the transposes during serialization.
# NetCDF4 supports large PCT arrays without the classic NetCDF size restrictions.
fname_new = 'landuse.timeseries_r025_hist_simyr1850-2015_c261005_50pfts_1850REBAL.nc'
ds_new.to_netcdf(fname_new, engine='netcdf4', format='NETCDF4')
print("File successfully rebalanced for 1850 baseline:", fname_new)
