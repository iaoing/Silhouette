# Silhouette - Build from Scratch

TODO

## Structure of Project

```
codebase/
├── result_analysis             # scripts to analyze result
│   ├── plot
│   │   └── in_flight_stores    # plot the CDF figure of in-flight stores
│   └── silhouette
│       └── scripts
|           └── in_flight_store_analysis    # script to analyze in-flight stores
├── scripts
│   ├── cache_sim
│   │   └── witcher     # the cache simulator imported from Witcher, with some modifications
│   ├── cheat_sheet     # the annotation for mechansism detection
│   │   ├── base        # the base annotation class
|   |   |   ├── cheat_base.py           # base annotation class
|   |   |   └── computation_sheet.py    # the class to support simple arithmetic operations
│   │   ├── nova        # the annotation class for nova
│   │   ├── pmfs        # the annotation class for pmfs
│   │   └── winefs      # the annotation class for winefs
│   ├── crash_plan
│   │   ├── crash_plan_entry.py             # the crash plan class
│   │   ├── crash_plan_gen.py               # the base class of the crash plan generator
│   │   ├── crash_plan_pm_data.py           # the class of PM data that are used for replaying
│   │   ├── crash_plan_scheme_2cp.py        # the 2CP crash plan generator
│   │   ├── crash_plan_scheme_base.py       # the base class of crash plan generator scheme
│   │   ├── crash_plan_scheme_comb.py       # the Combinatorial crash plan generator
│   │   ├── crash_plan_scheme_mech2cp.py    # the Mechanism + 2CP (a.k.a., Silhouette) crash plan generator
│   │   ├── crash_plan_scheme_mechcomb.py   # the Mechanism + Combinatorial (a.k.a., Invariants + Comb) crash plan generator
│   │   ├── crash_plan_type.py              # types of crash plans
│   │   ├── print_one_crash_plan.py         # helper functions to print a crash plan
│   │   ├── print_pm_data.py                # helper functions to print PM data
│   ├── executor            # the program entrance (main function)
│   │   ├── guest_side      # the guest-side scripts
│   │   │   ├── deduce_data_type.py         # wrapper functions to tag the data type
│   │   │   ├── deduce_mech.py              # wrapper functions to deduce mechanisms
│   │   │   ├── dedup.py                    # wrapper functions
│   │   │   ├── generate_crash_image.py     # wrapper functions to construct crash images
│   │   │   ├── generate_crash_plan.py      # wrapper functions to generate crash plans
│   │   │   ├── main_guest.py               # the main function to run on the guest
│   │   │   ├── tracing.py                  # functions to run the executable (test cases) and get the trace
│   │   │   └── validate_image.py           # functions to validate a crash image
│   │   ├── host_side       # the host-side scripts
│   │   │   ├── main_host.py                # the main function to run on the host
│   │   │   ├── print_memcached_info.py     # print the status of the running main host script
│   │   │   └── result_analysis
│   │   │       ├── dump_all.sh             # the script to analyze everything and produce the human-readable result
│   │   │       └── xxxx.py                 # other scripts to dump and analyze the result that are stored in memcached
│   ├── fs_conf         # the configuration for running Silhouette
│   │   ├── base        # the base class of configurations
│   │   ├── nova        # nova configuration
│   │   ├── pmfs        # pmfs configuration
│   │   ├── sshkey      # the sshkey to access the provided guest VM
│   │   └── winefs      # winefs configuration
│   ├── mech_reason             # mechanism detection
│   │   ├── mech_link           # detect links
│   │   ├── mech_lsw            # detect log-structured writes
│   │   ├── mech_memcpy         # detect memory copies
│   │   ├── mech_memset         # detect memory sets
│   │   ├── mech_replication    # detect replication
│   │   ├── mech_store          # detect PM stores
│   │   └── mech_undojnl        # detect undo journal
│   ├── shell_wrap                  # command wrapper to run shell commands
│   │   ├── scp_wrap.py             # wrappers to run SCP commands
│   │   ├── shell_cl_state.py       # shell command state
│   │   ├── shell_cmd_helper.py     # predefined shell commands
│   │   ├── shell_local_run.py      # run shell command on local machine
│   │   └── shell_ssh_run.py        # run shell command on remote by using SSH
│   ├── trace_proc                      # read and parse the execution trace
│   │   ├── instid_srcloc_reader        # match the instruction ID with the source location
│   │   ├── pm_trace                    # determine PM trace (e.g., flush, PM stores) in the execution trace
│   │   ├── trace_reader                # read and parse the execution trace
│   │   ├── trace_split                 # split the trace by file system operations
│   │   └── trace_stinfo                # analyze GEP trace and tag structure names and fields
│   ├── utils
│   │   ├── const_var.py        # constant variables
│   │   ├── exceptions.py       # exceptions
│   │   ├── logger.py           # logger
│   │   ├── proc_state.py       # the state of a running process (e.g., the QEMU instance)
│   │   ├── resource_record.py  # record consumed resource
│   │   └── utils.py            # misc utils
│   ├── vm_comm                         # communication with the gust VM
│   │   ├── heartbeat_guest.py          # heartbeat server runs on the guest
│   │   ├── heartbeat_host.py           # heartbeat checking function used on the host
│   │   ├── memcached_lock.py           # the distributed lock based on memcached
│   │   ├── memcached_wrapper.py        # function wrappers of memcached commands
│   └── vm_mgr                              # manage VMs
│       ├── guest_exception_handler.py      # exceptions used on the guest
│       ├── guest_signal_handler.py         # signal handler used on the guest
│       ├── guest_state.py                  # the state of a VM
│       ├── socket_port.py                  # find the available port for a VM
│       ├── ssh_config.py                   # manage the ssh config file for VMs
│       ├── vm_config.py                    # the arguments passed to QEMU
│       ├── vm_instance.py                  # the VM instance class
│       └── vm_mgr.py                       # the VM manager
├── tools
│   ├── disk_content                    # dump the state of all file/dir in a dir
│   │   ├── DiskContent.cpp             # the lib
│   │   ├── DiskContent.h
│   │   ├── disk_content_wrap.py        # wrapper for Python
│   │   ├── DumpDiskContent.cpp         # the main function
│   │   └── Makefile
│   ├── md5                 # the md5 lib to summarize a file
│   │   ├── LICENSE
│   │   ├── Makefile
│   │   ├── md5_wrap.py     # the wrapper for Python
│   │   ├── README.md
│   │   └── src
│   ├── README.md
│   ├── scripts                 # Python scripts
│   │   ├── disk_content        # dump the state of all file/dir in a dir
│   │   ├── src_info_reader     # read the source location information of instructions
│   │   └── struct_info_reader  # read the structure layout (structure declartion)
│   ├── src_info                # LLVM pass to dump the source location information of instructions
│   │   ├── DumpSrcInfo.cpp     # the LLVM pass
│   │   ├── Makefile
│   │   ├── SrcInfoReader.cpp   # the lib
│   │   └── SrcInfoReader.h
│   ├── struct_layout_ast       # dump the structure layout by the AST
│   │   ├── DumpStructLayout.cpp
│   │   ├── Makefile
│   │   ├── StructLayout.cpp
│   │   └── StructLayout.h
│   └── struct_layout_pass      # LLVM pass to dump the structure layout
│       ├── DumpStructLayout.cpp
│       ├── DumpStructLayout.h
│       ├── Makefile
│       ├── StructLayout.cpp
│       └── StructLayout.h
├── trace                   # code to instrument and build the FS module
│   ├── build-llvm15
│   │   └── Makefile        # the main makefile to instrument and build modules
│   ├── include
│   │   ├── Giri
│   │   ├── Si
│   │   └── Utility
│   ├── README.md
│   ├── runtime             # the runtime library for tracing
│   │   ├── NOVA
│   │   ├── pmfs
│   │   └── winefs
│   ├── src                 # implemented LLVM passes
│   │   ├── Giri
│   │   ├── Si
│   │   └── Utility
└── workload                # workload generator
    ├── ace                 # the ACe workload generator
    │   ├── ace
    │   ├── Makefile
    │   ├── README.md
    │   ├── tests           # the dir to store the base classes and generated test cases
    │   │   ├── ace-base                # the base classes of the origin ACE
    │   │   ├── ace-base-chipmunk       # the base classes for Chipmunk
    │   │   ├── ace-base-silhouette     # the base classes for Silhouette
    │   │   ├── BaseTestCase.cpp
    │   │   └── BaseTestCase.h
    │   └── user_tools
    ├── custom_workload     # examples of the custom workloads
    │   ├── base_ops
    │   ├── common
    │   └── NOVA
    ├── filesystem_operations   # the basic FS operations
    │   ├── fs_operations.py
    │   └── fsop_type.py
    └── misc
        ├── add_mark_and_chkpt_to_j_files.py                # add marker and checkpoint to j-files (for Chipmunk)
        ├── build_unique_j_files_based_on_sil_result.py     # build unique test cases based on Silhouette's result
        ├── convert_ace_to_vinter_tests.py                  # convert ACE test cases for Vinter
        ├── remove_symlink_j_files.py                       # remove symlinks from j-files
        ├── remove_symlink_yaml.py                          # remove symlinks from Vinter supported yaml files
        ├── sample_files.py                                 # sample the test cases based on a seed
        ├── sanitize_j_lang_for_chipmunk.py                 # sanitize j-lang files for Chipmunk
        └── shuffle_files.py                                # shuffle test cases based on a seed

```