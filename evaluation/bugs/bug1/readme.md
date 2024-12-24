# Bug 1 - Replica pointer not persisted correctly during inode allocation

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/154

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
    - Result sample: result/result_validation/cannot_write/nova_link-1.txt
        - The Crash Plan info
            ```txt
            #### cp:
            type: CrashPlanType.UnprotectedPersistOther
            inst id: 28018
            start seq: 8204
            persist seqs: [8204, 8217, 8222, 8226, 8230, 8233, 8242, 8261, 8264, 8269, 8273, 8323, 8353, 8409, 8422, 8427, 8431, 8435, 8438, 8447, 8466, 8469, 8474, 8478, 8528, 8953, 8954, 8956, 9003, 9014, 9219, 9220, 9222, 9269, 9280, 9355, 9447]
            expected data seqs: {9345}
            number of cps: 1
            info: seq: 9345, instid: 28018, struct: [0xffff888041502fe0, 0xffff888041503000, nova_inode_page_tail], vars: [__le64 alter_page], src: thirdPart/nova-chipmunk-disable-chipmunk-bugs/nova.h: 798, call path: ['nova_link', 'nova_append_link_change_entry', 'nova_append_log_entry', 'nova_get_append_head', 'nova_update_alter_pages']
            ```
        - The `demsg` log shows the log page tail error. This is because `pafe->alter_page` is NULL. Refer to [code](https://github.com/NVSL/linux-nova/blob/976a4d1f3d5282863b23aa834e02012167be6ee2/fs/nova/checksum.c#L225-L226).
            ```txt
            [  106.535474] nova_verify_entry_csum: log page tail error detected
            ```
        - This bug cause write failed, `write /mnt/pmem0/foo error: [Errno 5] Input/output error`. Sometimes, it can also cause segfault if `curr_p` is not 0 in the [code](https://github.com/NVSL/linux-nova/blob/976a4d1f3d5282863b23aa834e02012167be6ee2/fs/nova/nova.h#L691-L702).

4. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the last run.
    - **Note** that the generated result will also be removed if run:
        ```shell
        ./clean_up.sh
        ```
    - **Note** that if you would like to keep the generated result and log files, run
        ```shell
        ../../cleanup_for_testing.sh
        ```


