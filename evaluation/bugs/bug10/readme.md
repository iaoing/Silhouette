# Bug 10 - Unsafe user space read in procfs

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/149


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
    - Result sample: result/result_tracing/unknown_stat_error/case_2.sh.txt
            ```txt
            [   65.282778] RIP: 0010:vsscanf+0x4f6/0x1220
            [   65.283544] Code: 87 20 0f 85 16 fc ff ff 4c 89 f7 e8 a4 e7 2e ff 41 80 3f 00 0f 84 04 fc ff ff 49 ff c7 49 ff c6 eb c1 4c 89 ff e8 8a e7 2e ff <41> 80 3f 00 4c 8b 6c 24 48 0f 84 9d 0c 00 00 48 8d bc 24 20 01 00
            [   65.286827] RSP: 0018:ffff88820188f7a0 EFLAGS: 00010282
            [   65.287781] RAX: 4b771a2985bf4800 RBX: ffffffffc1297e43 RCX: ffffffff8712a626
            [   65.289042] RDX: 0000000000000000 RSI: 0000000000000001 RDI: 00005599f4d93630
            [   65.290302] RBP: ffff88820188f970 R08: dffffc0000000000 R09: ffff88820188f440
            [   65.291580] R10: dffffc0000000001 R11: ffffed1040311e8c R12: ffff88820188f880
            [   65.292846] R13: 000000000000006c R14: ffffffffc1297e42 R15: 00005599f4d93630
            [   65.294112] FS:  00007f6a12a4d580(0000) GS:ffff88822c800000(0000) knlGS:0000000000000000
            [   65.295579] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
            [   65.296617] CR2: 00005599f4d93630 CR3: 000000020c330002 CR4: 0000000000760ef0
            [   65.297887] DR0: 0000000000000000 DR1: 0000000000000000 DR2: 0000000000000000
            [   65.299156] DR3: 0000000000000000 DR6: 00000000fffe0ff0 DR7: 0000000000000400
            [   65.300423] PKRU: 55555554
            [   65.300951] Call Trace:
            [   65.301438]  ? xas_create+0x38f/0x620
            [   65.302131]  ? bprintf+0xe0/0xe0
            [   65.302749]  ? kernel_write+0x7b/0xa0
            [   65.304379]  ? write_sv_file+0x3af/0x420 [nova]
            [   65.305223]  sscanf+0xa8/0xf0
            [   65.305798]  ? _raw_spin_trylock_bh+0x40/0x40
            [   65.306604]  ? _raw_spin_lock+0x9b/0x100
            [   65.307337]  ? skip_atoi+0x60/0x60
            [   65.308927]  ? trace_start_calls+0xc1/0xd0 [nova]
            [   65.310740]  nova_seq_delete_snapshot+0x455/0x6d0 [nova]
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
