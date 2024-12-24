#!/bin/bash

set -e

mnt_point=$1
dump_disk_content_exe=$2
fs_state_store_dir=$3

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

make -C "$SCRIPT_DIR/../../base_ops"

sudo touch "$mnt_point/file"
sudo "$dump_disk_content_exe" "$mnt_point" "$fs_state_store_dir/oracle_01_open.txt" "create $mnt_point/file"

# sudo dd if=/dev/zero of="$mnt_point/file" bs=4096 count=2
sudo "$SCRIPT_DIR/../../base_ops/test_append.exe" "$mnt_point/file" 10
sudo "$dump_disk_content_exe" "$mnt_point" "$fs_state_store_dir/oracle_02_append.txt" "append $mnt_point/file 10"

# echo abcdefghij | sudo tee -a "$mnt_point/file" > /dev/null
sudo "$SCRIPT_DIR/../../base_ops/test_append.exe" "$mnt_point/file" 10
sudo "$dump_disk_content_exe" "$mnt_point" "$fs_state_store_dir/oracle_03_append.txt" "append $mnt_point/file 10"
