#!/bin/bash

arch -x86_64 /bin/bash --login -c '
  source /Users/jinyuntang/miniforge3/etc/profile.d/conda.sh
  conda activate /Users/jinyuntang/miniforge3/envs/e3sm-unified
  exec /bin/bash --noprofile --norc -i
'
