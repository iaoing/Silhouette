# Test snapshot
# Ignored NEXT_PAGE flag in the function nova_background_clean_snapshot_list
# https://github.com/NVSL/linux-nova/issues/138

set -e

sudo mkdir /mnt/pmem0/dir
sudo touch /mnt/pmem0/dir/file_1
sudo sh -c 'echo 1 > /proc/fs/NOVA/pmem0/create_snapshot'
sudo touch /mnt/pmem0/dir/file_2
sudo sh -c 'echo 1 > /proc/fs/NOVA/pmem0/create_snapshot'
sudo rm /mnt/pmem0/dir/file_1
sudo sh -c 'echo 1 > /proc/fs/NOVA/pmem0/create_snapshot'
sudo rm /mnt/pmem0/dir/file_2
sudo sh -c 'echo 1 > /proc/fs/NOVA/pmem0/create_snapshot'

sudo sh -c 'echo 0 > /proc/fs/NOVA/pmem0/delete_snapshot'
sudo sh -c 'echo 1 > /proc/fs/NOVA/pmem0/delete_snapshot'

sudo sh -c 'echo 2 > /proc/fs/NOVA/pmem0/delete_snapshot'
sudo sh -c 'echo 3 > /proc/fs/NOVA/pmem0/delete_snapshot'
sudo rm -rf /mnt/pmem0/dir