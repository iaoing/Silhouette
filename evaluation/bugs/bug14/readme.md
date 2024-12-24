# Bug 14 - Garbage collection information not updated atomically

## Description

Bug report: TBD

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
    - Result sample: result/result_validation/mismatch_old_value/nova_create-1.txt
        - `num_entries` is a variable used for GC.
        ```txt
        info: seq: 5662, instid: 26867, struct: [0xffff888041501fe0, 0xffff888041502000, nova_inode_page_tail], vars: [__le32 num_entries], src: thirdPart/nova-chipmunk-disable-chipmunk-bugs/nova.h: 756, call path: ['nova_create', 'nova_add_dentry', 'nova_append_dentry', 'nova_append_log_entry']
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

