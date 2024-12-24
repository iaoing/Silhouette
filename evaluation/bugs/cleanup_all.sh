#!/bin/bash

for dir in "./bug"*/; do
    if [ -d "$dir" ]; then
        echo "Entering directory: $dir"
        cd "$dir"
        ./clean_up.sh
        cd -
    fi
done
