# Bug Reproduction

## Run

Since some bugs may block other bugs, we make separate tests for each one. The bug number is the same as shown in the paper. Bug reports can be found in the `readme.md` file inside each subdirectory.

- Reproduce all bugs by one click:

    - This process may take ~2 hours.
    ```shell
    ./reproduce_all.sh
    ```

- Reproduce one specific bug:
    - Go to the bug directory and follow the `readme.md` file.
    - Each reproduction may take ~10-15 mins.

- Why does bug reproduction take so long?
    - Since some bugs may block other bugs, we make separate tests for each one.
    - Regardless of the number of test cases, Silhouette follows the same process to prepare virtual machines (VMs). As a result, over 90% of the time is spent setting up the VM for each bug reproduction.

## Troubleshots

- Clean up running tests if the reproduction process existed in errors or if you would like to stop the test early:
    ```shell
    # 1. kill the running script in needed
    pkill -f run.sh
    pkill -f run_all.sh
    pkill -f reproduce_all.sh

    # 2. clean up
    ../cleanup_for_testing.sh
    ```

- Disable all bugs in case the reproduction process exit in failures:
    ```shell
    ./disable_all_bugs.sh
    ```

- Clean up all generated results:
    ```shell
    ./cleanup_all.sh
    ```

## False Positives

1. ReplInvariantErrorType.NO_STORE_TO_PRIMARY

    - file system: NOVA-fortis
    - test cases: seq1_11func_bin/j-lang7, etc.
    - function: nova_dax_file_write
    - why reported: Silhouette did not find the stores to the primary data structure.
    - why false positive: As mentioned in the paper, we assume that replicas are synchronized using the `memcpy` instruction. However, in some cases, the store to the primary is also made by `memcpy`. Thus, Silhouette will consider the `memcpy` is a sync operation that copies data from the primary to the replica and will fail to find the stores to the supposed primary.
    - how to avoid the alarm: Handling this situation, copying from DRAM to both the PM primary and replica, in the `mech_repl_reason` file. In detail, if the source addresses and sizes of two to-PM copies are the same, Silhouette should consider they are the copies to the primary and the replica. (TODO)

2. UndoJnlInvariantErrorType.NO_IN_PLACE_WRITE

    - file system: NOVA-fortis
    - test cases: seq1_11func_bin/j-lang36, etc.
    - function: nova_rename
    - why reported: Conceptually, if data is journaled, it should be updated then. Silhouette detected that there are no corresponding in-writes to the journaled data.
    - why false positive: To fix a bug detected by Chipmunk ([issue](https://github.com/NVSL/linux-nova/issues/119)), NOVA journals some variables that won't be updated in some situations ([commit](https://github.com/NVSL/linux-nova/commit/6d1dfd730b31e81a33703f76e2ca34cbf634580f), [code](https://github.com/NVSL/linux-nova/blob/976a4d1f3d5282863b23aa834e02012167be6ee2/fs/nova/journal.c#L279-L287)), leading to this false positive reported by Silhouette.
    - how to avoid the alarm:
        - Since `NO_IN_PLACE_WRITE` is a performance issue, disabling this invariant check is okay.
        - Otherwise, rewrite the logic to avoid journaling unnecessary variables.
