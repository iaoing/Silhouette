# Bug 13 - Reuse inode in orphan list

## Description

Bug report: https://github.com/utsaslab/WineFS/issues/26

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
    - Result sample: result/result_validation/mismatch_both_oracle/pmfs_create-1.txt
        - The '.' and '..' files are gone when comparing the recovered state with either pre-operation state or post-operation state.
        ```txt
        #### other_msg:
        compare with prev-op state (- is recovered stat):
        diff: /mnt/pmem0/A/C <-> /mnt/pmem0/A/C
        - File_#Blocks : 0
        + File_#Blocks : 1
        - File_TotalSize : 0
        + File_TotalSize : 4096

        diff: ???? <-> /mnt/pmem0/A/C/.

        diff: ???? <-> /mnt/pmem0/A/C/..

        compare with post-op state (- is recovered stat):
        diff: /mnt/pmem0/A/C <-> /mnt/pmem0/A/C
        - File_#Blocks : 0
        + File_#Blocks : 1
        - File_TotalSize : 0
        + File_TotalSize : 4096

        diff: ???? <-> /mnt/pmem0/A/C/.

        diff: ???? <-> /mnt/pmem0/A/C/..

        diff: ???? <-> /mnt/pmem0/A/C/bar
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

