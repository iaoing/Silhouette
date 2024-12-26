# Silhouette Artifact

Artifact of the paper "Silhouette: Leveraging Consistency Mechanisms to Detect Bugs in Persistent Memory-Based File Systems" from USENIX FAST '25.


There are two ways to evaluate this artifact, by using [Chameleon Trovi](https://chameleoncloud.readthedocs.io/en/latest/technical/sharing.html) or a local machine.

## Option A. Chameleon Cloud (Recommended)

[Silhouette Artifact at Chameleon Trovi](https://www.chameleoncloud.org/experiment/share/3c807f1d-80db-443c-8d88-c645fa3695e8)

You can also find a copy of the JupyterLab script at [silhouette_ae.ipynb](https://github.com/iaoing/Silhouette/blob/main/silhouette_ae.ipynb)

To access Chameleon Cloud resources, you may need an account (anonymous to the artifact owner) to log in to Chameleon Cloud. You also need to have a project (budget) to allocate resources (e.g., node).

Chameleon provides [Day Pass](https://chameleoncloud.readthedocs.io/en/latest/technical/daypass.html) to test artifacts. However, the day pass requires the application to and approval from the artifact owner (us) so that the day pass is not anonymous.

As FAST '25 artifact reviewers, you should have the account distributed or the project (budget) assigned by the FAST AE committee to comply with the single-bind policy. If you do not have it, please contact the committee.

## Option B. Personal Machine

### 1. Platform

If you are using a personal machine (e.g., a virtual machine, a remote node, a local PC), please make sure:
- Hardware:
    - Support KVM (Silhouette may work without KVM, but we did not test it. You may need to modify some code in `Silhouette/codebase/scripts/vm_mgr/vm_instance.py` to make sure QEMU can start if your hardware or OS does not support KVM).
    - CPU: We tested Silhouette only on the CPU that supports Persistent Memory ([list](https://www.intel.com/content/www/us/en/support/articles/000055996/memory-and-storage/intel-optane-persistent-memory.html)). You may need to modify some code in `Silhouette/codebase/scripts/vm_mgr/vm_instance.py` to make sure QEMU can start if your hardware does not support PM.
- Ubuntu-22.x:
    - Silhouette works on any Linux systems, but other systems may have different versions of packages, which may differ from the setups shown here.
- Python-3.10.x:
    - You are free to install Python by `apt` or `pyenv`. Since Silhouette relies on `ctypes` and `readline`, please ensure the installed Python version includes these modules. Other Python versions are not tested and may not work if some packages/functions are deprecated over time.

### 2. Prepare Codebase and VM

Open a terminal and then execute the below commands.

```shell
# 2.1 Clone Silhouette Repo
mkdir -p ~/silhouette_ae
cd ~/silhouette_ae
git clone https://github.com/iaoing/Silhouette.git
```

A prepared guest VM is available at [Zenodo](https://zenodo.org/records/14550794).
What inside this guest VM:
- The installed kernel-5.1 (compiled by LLVM) with support to NOVA, PMFS, and WineFS modules.
- Some pre-built ACE workload.
- The Silhouette code is not inside the VM. They are scp-ed to the VM during running.
- You may log in to the VM to check what inside it by use the username `bing` and the key in `Silhouette/codebase/scripts/fs_conf/sshkey`.

Download a guest VM from Zenodo, ~30 GB
```shell
mkdir -p ~/silhouette_ae/qemu_imgs
cd ~/silhouette_ae/qemu_imgs
wget https://zenodo.org/records/14550794/files/silhouette_guest_vm.qcow2
```

Install Deps and Prepare
```shell
cd ~/silhouette_ae/Silhouette && bash ./install_dep.sh
cd ~/silhouette_ae/Silhouette && bash ./prepare.sh
```

Test the downloaded VM image:
- Use the below command to start the VM.
    ```shell
    qemu-system-x86_64 -machine pc-q35-focal,accel=kvm,nvdimm=on -cpu host -smp cpus=1 -m 4G,slots=8,maxmem=128G -enable-kvm -drive file=~/silhouette_ae/qemu_imgs/silhouette_guest_vm.qcow2,format=qcow2,index=0,media=disk -boot once=c -vnc :1 -net nic -net user,hostfwd=tcp::9001-:22 -daemonize
    ```
- Then, after 1 min (the VM may need 30s - 1min to boot), access the VM via SSH. The user name is `bing` and the pwd is `123456`. You may also use the [key](https://github.com/iaoing/Silhouette/tree/main/codebase/scripts/fs_conf/sshkey) to access it.
    ```shell
    ssh -p 9001 bing@localhost
    ```
- Do not remove the workload directories inside the VM image. It will affect the testing. You can use `qemu-img create` to snapshot it to avoid affecting the subsequent testing.
- At last, close the QEMU (e.g., `pkill`).

### 3. Reproduction

#### 3.1 Reproduce Bugs

The bug reproduction may take ~2 hours because:
- Some bugs may block other bugs, we make separate tests for each one.
- Regardless of the number of test cases, Silhouette follows the same process to prepare virtual machines (VMs). As a result, over 90% of the time is spent setting up the VM for each bug reproduction.

In a terminal, execute the belwo command:
```shell
cd ~/silhouette_ae/Silhouette/evaluation/bugs
nohup bash ./reproduce_all.sh &
```

When the test is done, please refer to `evaluation/bugs/bugXX/readme.md` in the git repo to check Silhouette output and the bug report and the detail of each bug (e.g., [Bug1](https://github.com/iaoing/Silhouette/blob/main/evaluation/bugs/bug1/readme.md)).

#### 3.2 Scalability Evaluation

The entire scalability test (as paper described) may take around one week. Thus, we provided two small tests here. Each of it needs to run about 4-5 hours. You may run all of them, or just one depends on your convenience. Also, you can modify the commands to run other tests.

**3.2.1 Test NOVA on ACE-seq3 workload with 20 VMs**

Since testing NOVA, PMFS, and WineFS on ACE-seq3 workload with different crash plan generation schemes (Silhouette, 2CP, Invariants+Comb) may take more than 40 hours, we only test NOVA with Silhouette scheme generation here.

This test takes ~4-5 hours. If you would like to run the entire seq3 workload, please refer to Section 3.3.

```shell
cd ~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp
nohup bash ./run.sh &
```

The result will be available in the `~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp/result` directory. Please refer to Section 3.2.3 to check the details of generated result.

Samples:
```shell
# This shows the time breakdown of this test.
cat ~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp/result/result_elapsed_time/result_time.txt
# This shows the number of generated crash plans
cat ~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp/result/result_cps/result.txt
```

**3.2.2 Test ACE-seq2 workload**

Testing one file system on ACE-seq2 workload with one crash plan generation scheme takes ~30 mins. Runing the entire seq2 workload takes around 4.5 hours. Therefore, we can run the entire seq2 workload and plot Figrue 1 and Table 9, similar to that presented in the paper. Running the entire seq3 workload my take ~3 days.

Figure 8 requires enabling certain bugs detected by Chipmunk and manual efforts to identify additional bugs, which may extend beyond the scope of this reproduction process.

Figure 9 contains parts of lines shown in Figure 1.

Since testing [Chipmunk](https://github.com/utsaslab/chipmunk) and [Vinter](https://github.com/KIT-OSGroup/vinter/tree/master) take longer time than Silhouette, and both tools have their artifacts available on GitHub, we will not discuss them further here.

```shell
# Run the test
# If your time allows, you can test ACE-seq3 workload
cd ~/silhouette_ae/Silhouette/evaluation/scalability/seq2
nohup bash ./run_all.sh &

# Analyze the result and plot the figrue and table
cd ~/silhouette_ae/Silhouette/evaluation/scalability/seq2
bash ./plot.sh

# Check the table
cat ~/silhouette_ae/Silhouette/evaluation/scalability/seq2/table_9.txt

# Check the figure
# You may need to use GUI or `scp` the figure to a local PC to view it.
```

**3.2.3 Raw Output Layout**

After testing, a `result` directory will be generated under each subdirectory (e.g., under `seq2/nova/mech2cp`), which contains the raw output.

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

## Troubleshot

- If any test exits with errors, you may need to check some files for integrity:
    - Run `bash evaluation/cleanup_for_testing.sh` to kill running processes and try to recover some configuration files
    - Check `~/.ssh/config` and remove newly added hosts
    - Remove `~/.ssh/config-yyyy.mm.dd.hh.mm.ss.ff` files if exist
    - Remove all code after the class definition in `codebase/scripts/fs_conf/base/env_base.py`
    - Remove all code after the class definition in `codebase/scripts/fs_conf/{FS}/env_{FS}.py`
- If the directories to store the codebase and the guest VM are different from the paths shown in the above examples, you may need to modify the [configuration files](https://github.com/iaoing/Silhouette/tree/main/codebase/scripts/fs_conf)
- If Memcached or QEMU requires running with the sudo privilege, you may need to modify some commands and some path in the [configuration files](https://github.com/iaoing/Silhouette/tree/main/codebase/scripts/fs_conf) to avoid the incorrect expand of ~ and permission issues.
