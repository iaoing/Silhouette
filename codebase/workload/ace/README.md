# ACE #
Ace is a bounded, and exhaustive workload generator for POSIX file systems. A workload is simply a sequence of file-system operations.

### Source ###
This codebase is derived from Chipmunk. We made some modifications to use it in our framework.

### Build ####
```bash
# generate j-lang files
python ace.py -t pm -l <seq_num>

# generate cpp files based on j-lang files
python3 cmAdapterParallel.py --i <path_to_seq_dir> -n <number_of_threads>

# make cpp files executable
make SEQ_DIR=<path_to_seq_dir> OUT_DIR=<path_of_bin> -j8
```

### Reference ###
1. https://github.com/utsaslab/chipmunk
2. https://github.com/utsaslab/crashmonkey/blob/master/docs/Ace.md
3. https://github.com/utsaslab/chipmunk/blob/main/chipmunk/executor/ace/ace.py
