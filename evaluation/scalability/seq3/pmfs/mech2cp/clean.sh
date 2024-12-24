#!/bin/bash
set -e
set -x

# 1. Clean up for testing
bash ../../../../cleanup_for_testing.sh

# 2. Remove result dir
rm -rf ./result
rm -f log.* nohup.out
