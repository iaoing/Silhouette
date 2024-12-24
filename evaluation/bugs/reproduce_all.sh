#!/bin/bash

set -x
set -e

for dir in "./bug"*/; do
    if [ -d "$dir" ]; then
        echo "Entering directory: $dir"
        cd "$dir"

        if [ -f "disable_bug.sh" ] && [ -f "enable_bug.sh" ] && [ -f "patch.diff" ]; then
            ./enable_bug.sh
            ./run.sh
            ./disable_bug.sh
        else
            ./run.sh
        fi

        cd -

        bash ../cleanup_for_testing.sh
        bash ./disable_all_bugs.sh
        # waiting for the release of the the listening port
        sleep 5
    fi
done
