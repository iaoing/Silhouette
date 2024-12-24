# Bug 3 - Replica pointer not persisted correctly during inode allocation

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/151

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
    - Result sample: result/result_details/j-lang4_20_nova_fallocate.txt
        - This file shows the last store's sequence (timestamp) is 14292 (the number may vary).
    - Result sample: result/result_validation/mismatch_old_value/nova_fallocate-6.txt
        - This file shows the crash plan persists all stores (includes 14292) so that the recovered state should be exactly as same as the post-operation state. However, it matches the pre-operation state and has data that mismatches the old value. This phenomenon indicates `fallcate` is inconsistent with the post-operation state.

4. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the last run.
    - **Note** that the generated result will also be removed if run:
        ```shell
        ./clean_up.sh
        ```
    - **Note** that if you would like to keep the generated result and log files, run
        ```shell
        ../../cleanup_for_testing.sh
        ```

