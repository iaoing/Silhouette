#!/bin/bash

set -x

pkill -e -f main_host.py
pkill -e -f qemu-system-x86
pkill -e -f memcached

set -e

ssh_config_bak=$(find ~/.ssh -type f -name "config.????.??.??.??.??.??.??????.bak")
if [ -z "$ssh_config_bak" ]; then
    echo "No matching ssh config bak file found."
else
    cp "$ssh_config_bak" ~/.ssh/config
    rm "$ssh_config_bak"
fi

find ~/ -type f -name "*.????????????????????.qcow2*" -exec rm {} +
