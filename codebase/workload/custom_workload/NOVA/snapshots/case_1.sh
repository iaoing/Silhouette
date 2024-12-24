# Test snapshot
# Incorrect epoch_id after restoring snapshot entries
# https://github.com/NVSL/linux-nova/issues/136

set -e

sudo touch /mnt/pmem0/file_1
sudo sh -c 'echo 1 > /proc/fs/NOVA/pmem0/create_snapshot'
sudo umount /mnt/pmem0

sudo mount -t NOVA -o dax,relatime,dbgmask=255 /dev/pmem0 /mnt/pmem0
sudo sh -c 'echo 1 > /proc/fs/NOVA/pmem0/create_snapshot'

sudo rm /mnt/pmem0/file_1
