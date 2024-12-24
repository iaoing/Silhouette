# Bug 6 - Atomicity violation in unlink and rmdir

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/148

## Detection Reproduction

1. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the past run.
    ```shell
    ./clean_up.sh
    ```

2. Run the script.
    ```shell
    ./run.sh
    ```
    - **Note** that this script, `run.sh`, has some hard-coded variables, such as the listening address and the port of the Memcached server, and the SSH config file. If you changed the `env_base.py` file, this script may need to be updated accordingly.

3. View the generated result.
    - Result sample: ./result/result_validation/mismatch_both_oracle/nova_unlink-1.txt
        - As described in the bug report, this bug causes the file becomes visible (dentry is visible) while the inode has been deleted.
        ```txt
        Path : /mnt/pmem0/A/foo
        Dir_Name   :
        Dir_Inode  : 18446744073709551615
        Dir_Offset : -1
        Dir_Length : 65535
        Dir_Type   : 0xff
        File_Inode     : 18446744073709551615
        File_TotalSize : -1
        File_BlockSize : -1
        File_#Blocks   : -1
        File_#HardLinks: 18446744073709551615
        File_Mode      : 4294967295
        File_User ID   : 4294967295
        File_Group ID  : 4294967295
        File_Device ID : 0
        File_RootDev ID: 66304
        File_MD5 : 0x
        stat /mnt/pmem0/A/foo error: No such file or directory

        stat /mnt/pmem0/A/foo error: No such file or directory
        ```

4. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the last run.
    - **Note** that the generated result will also be removed if run:
        ```shell
        ./clean_up.sh
        ```
    - **Note** that if you would like to keep the generated result and log files, run
        ```shell
        ../../cleanup_for_testing.sh
        ```




