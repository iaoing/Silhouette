# Bug 12 - O_APPEND doesn't work correctly

## Description

Bug report: https://github.com/NVSL/PMFS-new/issues/10

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
    - Result sample: result/result_validation/semantic_bug_file_size_after_append/pmfs_xip_file_write-1.txt
        ```txt
        #### other_msg:
        incorrect file size after append, append size: 10 bytes:
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

