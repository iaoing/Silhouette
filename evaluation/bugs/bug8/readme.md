# Bug 8 - Traversing snapshots fails after snapshot removal

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/138

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
    - Result sample: result/result_tracing/syslog_error/case_2.sh.txt
        ```txt
        [   70.055574] nova error:
        [   70.055595] unknown type 7, 0xffff8881f1617000, tail 0xffff88821ea36000
        [   70.056278] nova: assertion failed /home/bing/workplace/Silhouette/thirdPart/nova-chipmunk-disable-chi
        pmunk-bugs/snapshot.c:261: 0
        repeating...
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
