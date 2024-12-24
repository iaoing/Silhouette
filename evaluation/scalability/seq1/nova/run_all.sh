#!/bin/bash

set -x
set -e

for dir in "./"*/; do
    if [ -d "$dir" ]; then
        bash ../../../cleanup_for_testing.sh
        sleep 5

        echo "Entering directory: $dir"
        cd "$dir"

        if [ -f "run.sh" ]; then
            time ./run.sh
        fi

        cd -

        bash ../../../cleanup_for_testing.sh
        sleep 5
    fi
done
