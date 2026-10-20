import os
import numpy as np
from netCDF4 import Dataset

model     = 'elm'
case       = 'I20TRGSWCNPRDCTCBCTOPPHSWFMCROP_landg.r025'
startyear = 1850
endyear   = 1859
rundir   = '/home/ac.jtang/e3sm_run/scratch/chrys/'

myvars =    ['TLAI','EFLX_LH_TOT','GPP','NBP','NPP','QSOIL','QVEGT','QVEGE','QRUNOFF','TOTECOSYSC','TOTVEGC','TOTSOMC','TOTSOMN','TOTSOMP','FPG','FPG_P','TBOT','FSDS','RAIN','CPOOL','SR','RH2M']
scalefac =  [    8, 500,             12,   1 ,  6,      10,     10,     10,        10,    40000, 40000,  100000,    10000,     2000,    1,       1,    1,    350,   15,     4000, 6,   100]
scaletype=  [    2,   1,              2,   0,   1,       1,      1,      1,         2,     2,   2,       2,        2,        2,    2,       2,    3,      2,    2,     2,    2,     2] 

varlist = ''
for v in range(0,len(myvars)):
    varlist = varlist + myvars[v] + ','
varlist = varlist[:-1]

# ----- Create seasonal and annual mean climatology datasets -----
cmd_climo = 'ncclimo -c ' + case +' -m ' + model + ' -s ' + str(startyear) + ' -e ' + str(endyear) + ' -v ' + varlist + \
      ' -i ' + rundir + '/' + case + '/run/ -o ' + rundir + '/' + case + '/climo/'
      #' -i ' + rundir + '/' + case + '/archive/lnd/hist/ -o ' + rundir + '/' + case + '/climo/'
os.system(cmd_climo)

# ----- Create time-series datasets -----
myvars =    ['GPP','NEE','NPP','TOTVEGC','TOTSOMC','TOTECOSYSC']

varlist = ''
for v in range(0,len(myvars)):
    varlist = varlist + myvars[v] + ','
varlist = varlist[:-1]

myls=''
for y in range(startyear, endyear+1):
  yst = str(10000+y)[1:]
  myls = myls + ' ' + rundir + '/' + case + '/run/' + case + '.elm.h0.' + yst+'-??.nc'

