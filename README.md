# Silhouette Artifact

Artifact of the paper "Silhouette: Leveraging Consistency Mechanisms to Detect Bugs in Persistent Memory-Based File Systems" from USENIX FAST '25.

## 1. Prepare Platform

The artifact evaluation could be conducted on the Chameleon platform, offering three methods. It can also be tested on a personal machine (local, remote, or virtual machine).

- **[Log in to Chameleon with an Active Allocation](#log-in-to-chameleon-with-an-active-allocation)**
    - Reviewers need a Chameleon account with an active allocation (lease).
    - **Single-blind Caution:** The artifact owner may identify reviewers who access the artifact unless the conference committee provides anonymous Chameleon accounts.

- **[Apply for a Chameleon Day Pass](#apply-for-a-chameleon-day-pass)**
    - Reviewers can request a temporary day pass to access Chameleon without an active allocation.
    - No allocation is required, as resources are provisioned from the artifact owner's account.
    - **Single-blind Caution:** The artifact owner needs approve day-pass requests, potentially revealing the reviewers' email addresses, unless reviewers use anonymous email accounts to apply.

- **[Access a Pre-configured Chameleon Node via SSH](#access-a-pre-configured-chameleon-node-via-ssh)**
    - Reviewers can directly log in to a prepared Chameleon node using an SSH key provided in the HotCRP submission.
    - Anonymous login.

- **[Personal Machine](#personal-machine)**
    - Could be a local machine, a virtual machine, a could OS instance, etc.
    - Require additional efforts to setup.
    - Anonymous.

#### 1.1 Log in to Chameleon with an Active Allocation

#### 1.2 Apply for a Chameleon Day Pass

#### 1.3 Access a Pre-configured Chameleon Node via SSH

#### 1.4 Personal Machine

- Ubuntu-22.x
    Silhouette works on any Linux systems, but other systems may have different versions of packages, which may different from the setups shown here.
- Python-3.10.x
    You are free to install Python by `apt` or `pyenv`. Since Silhouette relies on `ctypes` and `readline`, please ensure the installed Python version includes these modules. Other Python versions are not tested and may not work if some packages/functions are deprecated over time.

## 2. Prepare Environment

- Install dependencies
    ```shell
    # You may want to see what will be installed before executing this script.
    ./install_dep.sh
    ```

- Download the code
    ```shell
    cd ~
    mkdir silhouette_ae
    cd silhouette_ae
    git clone https://github.com/iaoing/Silhouette
    ```

- Download a prepared virtual machine image
    - This VM image contains a prepared environment for testing NOVA, PMFS, and WineFS.
    ```shell
    cd ~
    cd silhouette_ae
    mkdir qemu_imgs
    cd qemu_imgs
    wget XXXX
    ```

## 3. Evaluation

1. Bug Reproduction
  Please refer to `evaluation/bugs/readme.md` for the details.

2. Silhouette Scalability
  Please refer to `evaluation/scalability/readme.md` for the details.
