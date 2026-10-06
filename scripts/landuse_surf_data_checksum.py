import numpy as np
import xarray as xr
import sys
import warnings
warnings.filterwarnings("ignore")

fpath = '/lcrc/group/e3sm/data/inputdata/lnd/clm2/surfdata_map/'
fname = 'landuse.timeseries_r025_hist_simyr1850-2015_c260808_50pfts.nc'

with xr.open_dataset(fpath + fname, chunks={'time': 1}) as ds:
    ds_new = ds.copy(deep=True)

# ---------------------------------------------------------
# 1850 Baseline Landuse Sum Rebalancing
# ---------------------------------------------------------
# Extract the 1850 crop value as a static 2D slice (lsmlat, lsmlon)
pct_crop_1850 = ds_new['PCT_CROP'].sel(time=1850).drop_vars('time', errors='ignore')
pct_urban_sum = ds_new['PCT_URBAN'].sum(dim='numurbl')

# Everything in this calculation is strictly 2D spatial now (no time dimension!)
suma = (ds_new['PCT_LAKE'] + ds_new['PCT_WETLAND'] + pct_urban_sum +
        ds_new['PCT_GLACIER'] + ds_new['PCT_NATVEG'] + pct_crop_1850)

deviation_mask = abs(suma - 100.0) > (2.0 * sys.float_info.epsilon)
scale = 100.0 / suma

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
# Restore original dimension order and save output
# ---------------------------------------------------------
# xarray can silently reorder dimensions during operations (e.g. cft moves to last).
# Restore each variable to match the input file's dimension order before writing,
# otherwise ELM will read data in the wrong order without any error.
with xr.open_dataset(fpath + fname) as ds_orig:
    for var in ds_new.data_vars:
        if var in ds_orig and ds_new[var].dims != ds_orig[var].dims:
            print(f'Restoring dim order for {var}: {ds_new[var].dims} → {ds_orig[var].dims}')
            ds_new[var] = ds_new[var].transpose(*ds_orig[var].dims)

# Force physical data reordering in memory (not just dimension names)
print("Rechunking to sync data layout with dimensions...")
ds_new = ds_new.compute()

fname_new = 'landuse.timeseries_r025_hist_simyr1850-2015_c261005_50pfts_1850REBAL.nc'
ds_new.to_netcdf(fname_new, format='NETCDF3_CLASSIC')
print("File successfully rebalanced for 1850 baseline:", fname_new)