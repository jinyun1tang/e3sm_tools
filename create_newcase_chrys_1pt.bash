#!/bin/bash
E3SM_ROOT=/lcrc/group/e3sm/ac.jtang/e3sm_20260806/
CASE=/home/ac.jtang/e3sm_run/scratch/chrys/failure_case/1pt_case_0910
POINT_DATA=/home/ac.jtang/e3sm_run/e3sm_tools/point_extract/output/1pt_10910

cd "$E3SM_ROOT/cime/scripts"
./create_newcase \
  --case "$CASE" \
  --compset I1850GSWCNPPHSWFMCROP \
  --res ELM_USRDAT \
  --mach chrysalis \
  --compiler intel \
  --pecount 1

cd "$CASE"


./xmlchange ELM_USRDAT_NAME=1x1pt_crop
./xmlchange ATM_DOMAIN_PATH="$POINT_DATA"
./xmlchange LND_DOMAIN_PATH="$POINT_DATA"
./xmlchange ATM_DOMAIN_FILE=domain_point_10910.nc
./xmlchange LND_DOMAIN_FILE=domain_point_10910.nc

./xmlchange RUN_TYPE=startup
./xmlchange CONTINUE_RUN=FALSE
./xmlchange RUN_STARTDATE=0001-01-01

./xmlchange DATM_CLMNCEP_YR_START=1901
./xmlchange DATM_CLMNCEP_YR_END=1920
./xmlchange DATM_CLMNCEP_YR_ALIGN=1

./xmlchange ATM_NCPL=48
./xmlchange STOP_OPTION=ndays,STOP_N=5
./xmlchange REST_OPTION=ndays,REST_N=1
./xmlchange DOUT_S=FALSE

cat > user_nl_elm <<EOF
paramfile = '/lcrc/group/e3sm/data/inputdata/lnd/clm2/paramdata/clm_params_c251006.nc'
fsurdat = '$POINT_DATA/surfdata_point_10910.nc'
finidat = '$POINT_DATA/initial_point_10910.nc'
flanduse_timeseries = '$POINT_DATA/landuse_point_10910.nc'
do_budgets = .true.
EOF

cat > user_nl_mosart <<EOF
 data_bgc_fluxes_to_ocean_flag = .true.
 parafile = '/lcrc/group/e3sm/data/inputdata/lnd/clm2/surfdata_map/global_reservoir_qd_20260706.nc'

 frivinp_rtm='/lcrc/group/e3sm/data/inputdata/rof/mosart/MOSART_global_qd_20240212.v3.nc'
EOF