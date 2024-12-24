#!/bin/bash

set -x
set -e

cd nova
bash ./clean_all.sh
cd -

cd pmfs
bash ./clean_all.sh
cd -

cd winefs
bash ./clean_all.sh
cd -

# Remove generated figures
rm -rf ./figures
