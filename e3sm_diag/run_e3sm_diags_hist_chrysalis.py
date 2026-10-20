import os
from e3sm_diags.parameter.core_parameter import CoreParameter
from e3sm_diags.run import runner

param = CoreParameter()

rundir   = '/home/ac.jtang/e3sm_run/scratch/chrys/'

# Location of the ref data.
refcase                   = 'I20TRGSWCNPRDCTCBCTOPPHSWFMCROP_landg.r025'
param.reference_data_path = rundir + '/' + refcase + '/climo'
param.reference_name      = refcase

param.ref_timeseries_input = False
# Years to slice the ref data, base this off the years in the filenames.
param.ref_start_yr = '1851'
param.ref_end_yr   = '1859'

# Location of the test data.
testcase                   = 'I20TRGSWCNPRDCTCBCTOPPHSWFMCROP_landg.r025'
param.test_data_path = rundir + '/' + testcase + '/climo'
param.test_name      = testcase

param.test_timeseries_input = False
# Years to slice the test data, base this off the years in the filenames.
param.test_start_yr = '1851'
param.test_end_yr   = '1859'

param.seasons = ['ANN', 'DJF', 'MAM', 'JJA', 'SON']

# What plotsets to run the diags on.
param.sets = ['lat_lon']

# Name of the folder where the results are stored.
# Change `prefix` to use your directory.
prefix = '/lcrc/group/e3sm/public_html/diagnostic_output/ac.jtang/I20TRGSWCNPRDCTCBCTOPPHSWFMCROP_landg.r025/'
param.results_dir = os.path.join(prefix, 'lat_lon')

# This parameter modifies the software to accommodate model vs model runs.
# The default setting for run_type is 'model_vs_obs'.
param.run_type = 'model_vs_model'

# Title of the difference plots.
param.diff_title = 'model - model'

# Below are more optional arguments.

# 'mpl' is to create matplotlib plots, 'vcs' is for vcs plots.
param.backend = 'mpl'
# For running with multiprocessing.
# param.multiprocessing = True
# param.num_workers = 32

# Use below to run all core sets of diags:
runner.sets_to_run = ['lat_lon', 'zonal_mean_xy', 'zonal_mean_2d', 'polar', 'cosp_histogram', 'meridional_mean_2d',
             'annual_cycle_zonal_mean', 'zonal_mean_2d_stratosphere', 'aerosol_aeronet', 'aerosol_budget']

# Use below to run lat_lon map only:
#runner.sets_to_run = ['lat_lon']
runner.run_diags([param])
