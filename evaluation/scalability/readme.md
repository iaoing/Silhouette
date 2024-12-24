# Silhouette Scalability

## Description

We provide scripts to test the scalability of Silhouette with ACE-seq1, ACE-seq2, and ACE-seq3 workloads, including testing:

1. NOVA with the Silhouette (mech2cp) crash plan generation scheme
2. NOVA with the Invariant+Comb (mechcomb) crash plan generation scheme
3. NOVA with the 2CP (2cp) crash plan generation scheme
4. PMFS with the Silhouette (mech2cp) crash plan generation scheme
5. PMFS with the Invariant+Comb (mechcomb) crash plan generation scheme
6. PMFS with the 2CP (2cp) crash plan generation scheme
7. WineFS with the Silhouette (mech2cp) crash plan generation scheme
8. WineFS with the Invariant+Comb (mechcomb) crash plan generation scheme
9. WineFS with the 2CP (2cp) crash plan generation scheme

For seq1 workload:
  - 68 test cases.
  - Each test takes ~10 mins with 5 VMs.
  - The whole 9 tests take ~1.5 hours with 5 VMs.
  - More VMs does not improve the time too much due to the limited number of test cases.

For seq2 workload:
  - 4K test cases.
  - Each test takes ~30 mins with 20 VMs.
  - The whole 9 tests take ~4.5 hours with 20 VMs.
  - Since each VM image may occur ~5 GB disk space, 20 VMs is good to run on our prepared Chameleon node. You can try to use more VMs in testing if your environment has enough disk space and DRAM.

For seq3 workload:
  - 50K test cases.
  - Each test takes XXX mins with 20 VMs.
  - The whole 9 tests take ~XXX hours with 20 VMs.
  - Since each VM image may occur ~5 GB disk space, 20 VMs is good to run on our prepared Chameleon node. You can try to use more VMs in testing if your environment has enough disk space and DRAM.

Running an entire workload (e.g., seq1) generates Figure 1 and Table 9, as presented in the paper.

Figure 8 requires enabling certain bugs detected by Chipmunk and manual efforts to identify additional bugs, which may extend beyond the scope of this reproduction process.

Figure 9 contains parts of lines shown in Figure 1.

Since testing [Chipmunk](https://github.com/utsaslab/chipmunk) and [Vinter](https://github.com/KIT-OSGroup/vinter/tree/master) take longer time than Silhouette, and both tools have their artifacts available on GitHub, we will not discuss them further here.

## Setup

No additional setup is required when using the provided VM image and following the reproduction manual.

## Run

#### Test an entrie workload

```shell
# 1. Select a workload to tets, assuming selecting seq2 here.
cd seq2

# 2. Clean up old results.
#    This script will remove all results generated in subdirectories.
./cleanup_all.sh

# 3. Run.
#    This script may take ~4.5 hours (for seq2). Using nohup or tmux to run it.
nohup ./run_all.sh &

# 4. Plot.
#    This script will generate `figure_1.pdf` and `table_9.txt`.
./plot.sh

# 5. Check generated figures and tables.
#    figure_1.pdf needs to be copied to the local for viewing.
#    table_9.txt can be opened directly in the terminal.
less table_9.txt
```

#### Test a single test of a workload

**NOTE**: Testing a singe test will not generate figures and tables. All data are raw data.

```shell
# 1. Select a test to run.
#    Assuming test seq2/nova/mech2cp
cd seq2/mech2cp

# 2. Clean up old results.
#    This script will remove all results generated in subdirectories.
./cleanup_all.sh

# 3. Run.
#    This script may take ~30 mins (for seq2). Using nohup or tmux to run it.
nohup ./run_all.sh &
```

## Raw Result Layout

After the test, a `result` directory will be generated under each subdirectory (e.g., under `nova/mech2cp`), which contains the raw result.

```txt
├── result/
    ├── result_cache_sim/           -> stores the cache simulation result, e.g., the number of in-flight stores at each ordering point, the duplicate fences.
    ├── result_cps/                 -> stores the number of different types of crash plans.
    ├── result_cps2validation       -> stores short reports
    ├── result_details              -> stores the trace of stores, flushes, and fences in the order of timestamp. Each store are marked as rep (replication-related stores), lsw (Log-structure Write-related stores), jnl (journal-related stores), or nothing (unprotected store). It also contains the detailed info (which store should be persisted and which should be unpersisted) generated crash plans.
    ├── result_elapsed_time         -> the time breakdown. The total guest time is related to the number of running VMs.
    ├── result_failed_test_cases    -> summary of failed test cases (e.g., rename a dir as its parents)
    ├── result_invaraints           -> results of invariant checking (may contain false positives)
    ├── result_memcached_info       -> the states of memcached (e.g., number of sets)
    ├── result_tracing              -> error that happened during tracing (execution)
    ├── result_unique_ops           -> summary of unique operations
    ├── result_validation           -> the validation results
    └── result_vminfo.txt           -> the general info of running VMs
```
