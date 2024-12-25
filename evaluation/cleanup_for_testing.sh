#!/bin/bash

set -x

sudo pkill -e -f main_host.py
sudo pkill -e -f qemu-system-x86
sudo pkill -e -f memcached

set -e

ssh_config_bak=$(find ~/.ssh -type f -name "config.????.??.??.??.??.??.??????.bak")
if [ -z "$ssh_config_bak" ]; then
    echo "No matching ssh config bak file found."
else
    cp "$ssh_config_bak" ~/.ssh/config
    if [ $? -eq 0 ]; then
        rm "$ssh_config_bak"
    else
        echo "SSH config file restored failed, please manually check the config file and restore it."
    fi
fi

find ~/ -type f -name "*.????????????????????.qcow2*" -exec rm {} +
