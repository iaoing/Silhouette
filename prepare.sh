#!/bin/bash

cd codebase/scripts/fs_conf/sshkey
chmod 600 fast25_ae_vm
chmod 644 fast25_ae_vm.pub

cd -
cd codebase/tools/disk_content
make
