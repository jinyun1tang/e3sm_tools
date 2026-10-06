#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 18 09:37:46 2024

Make E3SM domain file for r0125 DATM data

@author: Zeli Tan
"""

import numpy as np
from netCDF4 import Dataset

# grids
nlon_fine = 2880
nlat_fine = 1440
lons_grid = 0.0625 + 0.125 * np.arange(nlon_fine)
lats_grid = -89.9375 + 0.125 * np.arange(nlat_fine)

xc = np.repeat(lons_grid[np.newaxis,:], nlat_fine, axis=0)
yc = np.repeat(lats_grid[:,np.newaxis], nlon_fine, axis=1)

xv = np.zeros((4,nlat_fine,nlon_fine))
yv = np.zeros((4,nlat_fine,nlon_fine))

xv[0] = xc - 0.0625
xv[1] = xc + 0.0625
xv[2] = xc + 0.0625
xv[3] = xc - 0.0625

yv[0] = yc - 0.0625
yv[1] = yc - 0.0625
yv[2] = yc + 0.0625
yv[3] = yc + 0.0625

mask = np.ones((nlat_fine,nlon_fine), dtype=np.int32)

la = 2.0 * np.pi * 0.125 / 360.0
lb = 2.0 * np.pi * 0.125 / 360.0
area = la * lb * np.cos(yc/180.0*np.pi)

filename = '/lcrc/group/e3sm/ac.ztan/user_inputdata/atm/datm7/' + \
    'atm_forcing.datm7.GSWP3-w5e5.0.125x0.125.c211106/domain.lnd.GSWP3-w5e5.r0125.c211106.nc'
try:
    nc = Dataset(filename, 'w', format='NETCDF3_64BIT_OFFSET')
    nc.case_title = "GSWP3-w5e5 6-Hourly 0.125x0.125 Atmospheric Forcing"
    nc.createDimension('scalar', 1)
    nc.createDimension('ni', nlon_fine)
    nc.createDimension('nj', nlat_fine)
    nc.createDimension('nv', 4)
    xc_var = nc.createVariable('xc', 'f8', ('nj','ni',))
    xc_var.long_name = "longitude of grid cell center"
    xc_var.units = "degrees_east"
    xc_var.mode = "time-invariant"
    xc_var[:] = xc
    yc_var = nc.createVariable('yc', 'f8', ('nj','ni',))
    yc_var.long_name = "latitude of grid cell center"
    yc_var.units = "degrees_north"
    yc_var.mode = "time-invariant"
    yc_var[:] = yc
    xv_var = nc.createVariable('xv', 'f8', ('nv','nj','ni',))
    xv_var.long_name = "longitude of grid cell vertices"
    xv_var.units = "degrees_east"
    xv_var.mode = "time-invariant"
    xv_var[:] = xv
    yv_var = nc.createVariable('yv', 'f8', ('nv','nj','ni',))
    yv_var.long_name = "latitude of grid cell vertices"
    yv_var.units = "degrees_north"
    yv_var.mode = "time-invariant"
    yv_var[:] = yv
    mask_var = nc.createVariable('mask', 'i4', ('nj','ni',))
    mask_var.long_name = "domain mask"
    mask_var.units = "unitless"
    mask_var.mode = "time-invariant"
    mask_var[:] = mask
    area_var = nc.createVariable('area', 'f8', ('nj','ni',))
    area_var.long_name = "area of grid cell in radians squared"
    area_var.units = "area"
    area_var.mode = "time-invariant"
    area_var[:] = area
finally:
    nc.close()

