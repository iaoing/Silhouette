#!/bin/bash

set -x
set -e

cd nova
time bash ./run_all.sh
cd -

cd pmfs
time bash ./run_all.sh
cd -

cd winefs
time bash ./run_all.sh
cd -
