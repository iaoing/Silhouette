# Bug 11 - DRAM inode structure not initialized

## Description

Bug report: https://github.com/NVSL/linux-nova/issues/146

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
    - Result sample: result/result_validation/get_post_oracle_remount_failed/nova_put_super-1.txt
        ```txt
        [   86.974941] RIP: 0010:check_memory_region+0x6f/0x2a0
        [   86.975871] Code: 03 49 ba 01 00 00 00 00 fc ff df 4f 8d 1c 11 4c 89 db 4c 29 e3 48 83 fb 10 7f 27 48
        85 db 0f 84 46 01 00 00 49 f7 d1 4d 01 f9 <41> 80 3c 24 00 0f 85 de 01 00 00 49 ff c4 49 ff c1 75 ed e9 2
        8 01
        [   86.979143] RSP: 0018:ffff8881d583f618 EFLAGS: 00010292
        [   86.980107] RAX: 000000000001ffff RBX: 000000000000000f RCX: ffffffffc11d80ee
        [   86.981389] RDX: 0000000000000001 RSI: 0000000000000078 RDI: ffff96406b9e31c0
        [   86.982679] RBP: ffff8881d583f638 R08: dffffc0000000000 R09: fffffffffffffff1
        [   86.983967] R10: dffffc0000000001 R11: ffffeec80d73c647 R12: ffffeec80d73c638
        [   86.985247] R13: 1ffff1103ab07ed8 R14: ffff888040401280 R15: 1ffff2c80d73c638
        [   86.986540] FS:  00007ff0296b0840(0000) GS:ffff88822c800000(0000) knlGS:0000000000000000
        [   86.988019] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
        [   86.989077] CR2: ffffeec80d73c638 CR3: 00000001d33c8005 CR4: 0000000000760ef0
        [   86.990365] DR0: 0000000000000000 DR1: 0000000000000000 DR2: 0000000000000000
        [   86.991655] DR3: 0000000000000000 DR6: 00000000fffe0ff0 DR7: 0000000000000400
        [   86.992939] PKRU: 55555554
        [   86.993498] Call Trace:
        [   86.994015]  kasan_check_write+0x14/0x20
        [   86.994827]  memcpy_to_pmem_nocache+0x1e/0x50 [nova]
        [   86.995813]  nova_free_inode_log+0x323/0x4c0 [nova]
        [   86.996783]  ? nova_free_contiguous_log_blocks+0x150/0x150 [nova]
        [   86.997955]  nova_recovery+0x1620/0x16d0 [nova]
        [   86.998869]  ? free_resources+0x100/0x100 [nova]
        [   86.999749]  ? xas_find_marked+0x3bf/0x430
        [   87.000541]  ? ida_alloc_range+0x5cb/0x620
        [   87.001324]  ? xas_error+0x11/0x40
        [   87.001995]  ? ida_alloc_range+0x5ee/0x620
        [   87.006180]  ? idr_replace+0x160/0x160
        [   87.010065]  ? kasan_check_write+0x14/0x20
        [   87.013962]  ? _raw_write_lock+0x9b/0x100
        [   87.017792]  ? nova_lite_journal_soft_init+0x198/0x5f0 [nova]
        [   87.021864]  ? nova_error_mng+0x190/0x190 [nova]
        [   87.025703]  ? nova_commit_lite_transaction+0x60/0x60 [nova]
        [   87.029696]  nova_fill_super+0xa17/0xcd0 [nova]

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

