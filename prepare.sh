#!/bin/bash

# After installing memcached, it will be auto started by the systemctl. Disabling it to avoid any issues.
sudo systemctl stop memcached
sudo systemctl disable memcached

cd codebase/scripts/fs_conf/sshkey
chmod 600 fast25_ae_vm
chmod 644 fast25_ae_vm.pub

cd -
cd codebase/tools/disk_content
make
