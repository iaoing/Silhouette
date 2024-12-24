# Bug 2 - Inconsistent inode attributes between PM and VFS cache.

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/153

## Detection Reproduction

1. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the last run.
    - **Note** that the generated result will also be removed.
    ```shell
    ./clean_up.sh
    ```

2. Run the script.
    - **Note** that this script, `run.sh`, has some hard-coded variables, such as the listening address and the port of the Memcached server, and the SSH config file. If you changed the `env_base.py` file, this script may need to be updated accordingly.
    ```shell
    ./run.sh
    ```

3. View the generated result.
    - Result sample: result/result_validation/mismatch_both_oracle/nova_symlink-1.txt
        ```txt
        #### other_msg:
        compare with prev-op state (- is recovered stat):
        diff: /mnt/pmem0/bar <-> ????

        compare with post-op state (- is recovered stat):
        diff: /mnt/pmem0/bar <-> /mnt/pmem0/bar
        - File_TotalSize : 15
        + File_TotalSize : 14
        - File_#Blocks : 1
        + File_#Blocks : 0
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

