# Bug 9 - Extent tree unreadable due to wrong checksum

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/137

## Detection Reproduction

1. Clean up the environment (e.g., running VMs, Memcached, the generated result, log files) in case we forgot to clean up after the last run.
    - **Note** that the generated result will also be removed.

    ```shell
    ./clean_up.sh
    ```

2. Run the script.
    ```shell
    ./run.sh
    ```
    - **Note** that this script, `run.sh`, has some hard-coded variables, such as the listening address and the port of the Memcached server, and the SSH config file. If you changed the `env_base.py` file, this script may need to be updated accordingly.


3. View the generated result.
    - Result sample: result/result_validation/cannot_write/nova_put_super-1.txt
        - The checksum checking failed so that NOVA cannot rebuild the extend-tree of the newly created file, leading to messing up attributes.
        ```txt
        [   89.148430] nova: nova_find_range_node: curr failed
        [   89.151092] nova: nova_range_node_checksum_ok: checksum failure, vma           (null), range low 1765074, range high 18446612683165798512, csum 0x0
        [   89.151094] nova: nova_find_range_node: curr failed
        [   89.151255] nova: nova_insert_range_node: type 3 entry 1765074 - 18446612683165798624 already exists: 1765074 - 18446612683165798512
        [   89.151261] nova: nova_insert_dir_tree ERROR -22: foo
        [   89.151262] nova error:
        [   89.151264] nova_create return -22
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

