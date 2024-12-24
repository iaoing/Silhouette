# Bug 7 - Snapshot ID set incorrectly during recovery

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/136

## Detection Reproduction

1. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the last run.
    ```shell
    ./clean_up.sh
    ```

2. Run the script.
    ```shell
    ./run.sh
    ```
    - **Note** that this script, `run.sh`, has some hard-coded variables, such as the listening address and the port of the Memcached server, and the SSH config file. If you changed the `env_base.py` file, this script may need to be updated accordingly.

3. View the generated result.
    - Result sample: result/result_validation/get_prev_oracle_remount_failed/nova_lookup-1.txt
        ```txt
        [  213.410381] nova: Restore snapshot epoch ID 0
        [  213.410407] nova: Restore snapshot epoch ID 0
        [  213.410419] nova: nova_insert_snapshot_info ERROR -17
        [  213.410421] nova: nova_restore_snapshot_entry: Restore snapshot epoch ID 0 failed
        [  213.410423] nova error:
        [  213.410424] Restore entry 0 failed
        [  213.411547] nova: Recovered 1 snapshots, latest epoch ID 0
        [  213.411549] nova: Initialize snapshot infos failed
        [  213.415153] nova error:
        [  213.415156] nova_fill_super: nova recovery failed with return code -17
        [  213.415966] nova: nova_fill_super failed: return -17
        [  213.416806] nova: Running snapshot cleaner thread
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
