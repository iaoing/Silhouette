# Bug 4 - Truncate is not atomic

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/152

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
    - Result sample: result/result_validation/mismatch_both_oracle/nova_notify_change-1.txt
        ```txt
        [   84.258148] nova error:
        [   84.258152] do_dax_mapping_read: nova data checksum and recovery fail! inode 33, offset 0, entry pgoff 0, 1 pages, pgoff 0

        compare with prev-op state (- is recovered stat):
        diff: /mnt/pmem0/foo <-> /mnt/pmem0/foo
        - File_TotalSize : 256
        + File_TotalSize : 4096
        - File_MD5 : 0x
        + File_MD5 : 0xca6f0b25289330ad8e608d1a219e663b

        compare with post-op state (- is recovered stat):
        diff: /mnt/pmem0/foo <-> /mnt/pmem0/foo
        - File_MD5 : 0x
        + File_MD5 : 0x0367a6779188575d1166c16944fe7136
        ```
        - This result sample is a little different from the description in the submitted version of the paper. This is because `truncate` is not atomic and we sampled memcpys here, so that the data checksum checks failed during recovery.
        - If we do not sample memcpys, the data checksum checks will be passed and the data leak issue will occur.

4. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the last run.
    - **Note** that the generated result will also be removed if run:
        ```shell
        ./clean_up.sh
        ```
    - **Note** that if you would like to keep the generated result and log files, run
        ```shell
        ../../cleanup_for_testing.sh
        ```

