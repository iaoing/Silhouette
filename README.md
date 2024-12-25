# Silhouette Artifact

Artifact of the paper "Silhouette: Leveraging Consistency Mechanisms to Detect Bugs in Persistent Memory-Based File Systems" from USENIX FAST '25.


There are two ways to evaluate this artifact, by using [Chameleon Trovi](https://chameleoncloud.readthedocs.io/en/latest/technical/sharing.html) or a local machine.

## Option A. Chameleon Cloud

[Silhouette Artifact at Chameleon Trovi](https://www.chameleoncloud.org/experiment/share/3c807f1d-80db-443c-8d88-c645fa3695e8)

You can also find a copy of the JupyterLab script at `silhouette_ae.ipynb`

## Option B. Personal Machine

### 1. Platform

If you are using a personal machine (e.g., a virtual machine, a remote node, a local PC), please make sure you have:
- Ubuntu-22.x
    Silhouette works on any Linux systems, but other systems may have different versions of packages, which may different from the setups shown here.
- Python-3.10.x
    You are free to install Python by `apt` or `pyenv`. Since Silhouette relies on `ctypes` and `readline`, please ensure the installed Python version includes these modules. Other Python versions are not tested and may not work if some packages/functions are deprecated over time.

### 2. Prepare Codebase and VM

Open a terminal and then execute the below commands.

```shell
# 2.1 Clone Silhouette Repo
mkdir -p ~/silhouette_ae
cd ~/silhouette_ae
git clone https://github.com/iaoing/Silhouette.git

# 2.2 Download VM from Zenodo, may take ~20 mins
mkdir -p ~/silhouette_ae/qemu_imgs
cd ~/silhouette_ae/qemu_imgs
wget https://zenodo.org/records/14550794/files/silhouette_guest_vm.qcow2

# 2.3 Install Deps and Prepare
cd ~/silhouette_ae/Silhouette && bash ./install_dep.sh
cd ~/silhouette_ae/Silhouette && bash ./prepare.sh
```

### 3. Reproduction

#### 3.1 Reproduce Bugs

The bug reproduction may take ~2 hours because:
- Some bugs may block other bugs, we make separate tests for each one.
- Regardless of the number of test cases, Silhouette follows the same process to prepare virtual machines (VMs). As a result, over 90% of the time is spent setting up the VM for each bug reproduction.

Please refer to `evaluation/bugs/readme.md` for the detailed instructions.

```shell
cd ~/silhouette_ae/Silhouette/evaluation/bugs
nohup bash ./reproduce_all.sh &
```

When the test is done, please refer to `evaluation/bugs/bug{XX}/readme.md` to check the output.

#### 3.2 Scalibility Evaluation

**3.2.1 Test NOVA on ACE-seq3 workload with 20 VMs**

Since testing NOVA, PMFS, and WineFS on ACE-seq3 workload with different crash plan generation schemes (Silhouette, 2CP, Invariants+Comb) may take more than 40 hours, we only test NOVA with Silhouette scheme generation here.

This test takes ~4-5 hours.

Please refer to `evaluation/scalability/readme.md` for the detailed instructions.

```shell
cd ~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp
nohup bash ./run.sh &
```

The result will be available in the `~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp/result` directory. please refer to the `Raw Result Layout` section in `evaluation/scalability/readme.md` to check the type generated result.

Samples:
```shell
# This shows the time breakdown of this test.
cat ~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp/result/result_elapsed_time/result_time.txt
# This shows the number of generated crash plans
cat ~/silhouette_ae/Silhouette/evaluation/scalability/seq3/nova/mech2cp/result/result_cps/result.txt
```

**3.2.2 Test ACE-seq2 workload**

Testing one file system on ACE-seq2 workload with one crash plan generation scheme takes ~30 mins. Therefore, we can run the entrie seq2 workload and plot Figrue 1 and Table 9, similar to that presented in the paper.

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
