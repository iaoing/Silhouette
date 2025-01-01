import os
import sys
import glob
import argparse
import shutil, errno
import re
import subprocess
import concurrent.futures
import multiprocessing
from tqdm import tqdm

def make_write_buf(buf_size):
    buf = "a" * buf_size
    return buf

def parse_fpath(fpath):
    # vinter's mount point is /mnt
    fpath.rstrip()
    rst = "/mnt"
    for i in range(len(fpath)):
        c = fpath[i]
        if c.isupper():
            rst += "/%c" % (c)
        else:
            rst += "/%s" % (fpath[i:])
            break
    # print("%s -> %s" % (fpath, rst))
    return rst

def one_cpu_task(tid, output_dir, j_lang_file_list, lower_idx, upper_idx, seq_dir):
    for idx in tqdm(range(lower_idx, upper_idx), desc=f'thd #{tid}'):
        fname = j_lang_file_list[idx]
        base_j_lang_fname = os.path.basename(fname)

        fd = open(fname, 'r')
        lines = fd.readlines()
        fd.close()


        trace_cmd_suffix = 'trace_cmd_suffix: "'
        checkpoint_range = 'checkpoint_range: [1, 2]'
        dump_cmd_suffix = 'dump_cmd_suffix: "ls /mnt"'
        file_create_set = set()
        found_run = False
        marked = False
        for line in lines:
            if line.startswith('# run'):
                found_run = True
                continue
            if found_run:
                if line.isspace():
                    continue
                line = line.lstrip()
                line = line.rstrip()
                items = line.split(' ')
                if items[0] == 'open':
                    if items[1] not in file_create_set:
                        # touch will call two system calls, create and chmod.
                        # if marked:
                        trace_cmd_suffix += " test_creat.exe %s &&" % (parse_fpath(items[1]))
                        # else:
                        #     trace_cmd_suffix += " > %s && chmod 777 %s &&" % (parse_fpath(items[1]), parse_fpath(items[1]))
                        file_create_set.add(items[1])
                elif items[0] == 'link':
                    trace_cmd_suffix += " ln %s %s &&" % (parse_fpath(items[1]), parse_fpath(items[2]))
                elif items[0] == 'mkdir':
                    trace_cmd_suffix += " mkdir %s -m 777 &&" % (parse_fpath(items[1]))
                elif items[0] == 'rmdir':
                    trace_cmd_suffix += " rmdir %s &&" % (parse_fpath(items[1]))
                elif items[0] == 'unlink':
                    trace_cmd_suffix += " unlink %s &&" % (parse_fpath(items[1]))
                    if items[1] in file_create_set:
                        file_create_set.remove(items[1])
                elif items[0] == 'remove':
                    trace_cmd_suffix += " rm %s &&" % (parse_fpath(items[1]))
                    if items[1] in file_create_set:
                        file_create_set.remove(items[1])
                elif items[0] == 'dwrite':
                    trace_cmd_suffix += " test_pwrite.exe %s %d %d &&" % (parse_fpath(items[1]), int(items[3]), int(items[2]))
                    # trace_cmd_suffix += " dd if=/dev/random of=%s ibs=4096 obs=1024 bs=%d count=1  seek=%d conv=notrunc &&" % (parse_fpath(items[1]), int(items[3]), int(items[2]))
                    # trace_cmd_suffix += " echo %s | dd bs=%d count=1 of=%s conv=notrunc oflag=direct seek=%d &&" % (make_write_buf(int(items[3])), int(items[3]), parse_fpath(items[1]), int(items[2]))
                elif items[0] == 'write':
                    trace_cmd_suffix += " test_pwrite.exe %s %d %d &&" % (parse_fpath(items[1]), int(items[3]), int(items[2]))
                    # trace_cmd_suffix += " dd if=/dev/random of=%s ibs=4096 obs=1024 bs=%d count=1  seek=%d conv=notrunc &&" % (parse_fpath(items[1]), int(items[3]), int(items[2]))
                    # trace_cmd_suffix += " echo %s | dd bs=%d count=1 of=%s conv=notrunc oflag=direct seek=%d &&" % (make_write_buf(int(items[3])), int(items[3]), parse_fpath(items[1]), int(items[2]))
                elif items[0] == 'rename':
                    trace_cmd_suffix += " mv %s %s &&" % (parse_fpath(items[1]), parse_fpath(items[2]))
                elif items[0] == 'symlink':
                    trace_cmd_suffix += " ln -s %s %s &&" % (parse_fpath(items[1]), parse_fpath(items[2]))
                elif items[0] == 'truncate':
                    trace_cmd_suffix += " truncate -s %d %s &&" % (int(items[2]), parse_fpath(items[1]))
                elif items[0] == 'falloc':
                    trace_cmd_suffix += " test_fallocate.exe %s %s %s 1 &&" % (parse_fpath(items[1]), items[3], items[4])
                elif items[0] == 'opendir':
                    trace_cmd_suffix += " ls %s &&" % (parse_fpath(items[1]))
                elif items[0] == 'close':
                    pass
                elif items[0] == 'none':
                    pass
                elif items[0] == 'mark':
                    marked = True
                    trace_cmd_suffix += " hypercall checkpoint 1 &&"
                elif items[0] == 'checkpoint':
                    trace_cmd_suffix += ' hypercall checkpoint 2"'
                    break
                else:
                    print("[", items[0], "]")
                    print(line)
                    print(fname)
                    assert False

        trace_cmd_suffix.rstrip("&")

        # print(fname)
        # print(trace_cmd_suffix)
        ofname = "%s/%s.yaml" % (output_dir, base_j_lang_fname)
        with open(ofname, 'w') as fd:
            fd.write(trace_cmd_suffix + "\n")
            fd.write(checkpoint_range + "\n")
            fd.write(dump_cmd_suffix + "\n")

    return 0

def main():
    if len(sys.argv) != 4:
        print("usage: python3 this_script.py seq_dir_path output_dir num_cpus")
        exit(0)

    seq_dir = sys.argv[1]
    output_dir = sys.argv[2]
    num_cpus = int(sys.argv[3])

    max_cpus = multiprocessing.cpu_count()
    if num_cpus == 0 or num_cpus >= max_cpus:
        num_cpus = max_cpus - 1

    j_lang_file_list = []
    for f in glob.glob(seq_dir + "/j-lang-files/j-lang*"):
        j_lang_file_list.append(f)


    if num_cpus == 1:
        one_cpu_task(0, output_dir, j_lang_file_list, 0, len(j_lang_file_list), seq_dir)

    elif num_cpus > 1:
        files_per_cpu = len(j_lang_file_list)//num_cpus
        range_cpus = []
        for i in range(num_cpus):
            # one cpu runs on [lower_idx, upper_idx)
            lower_idx = i * files_per_cpu + 1
            upper_idx = (i + 1) * files_per_cpu + 1
            if i == 0:
                lower_idx = 0
            if i + 1 == num_cpus:
                upper_idx = len(j_lang_file_list)
            range_cpus.append([lower_idx, upper_idx])

        print(range_cpus)
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_cpus) as executor:
            # Submit tasks to the thread pool
            future_to_task = {executor.submit(one_cpu_task, i, output_dir, j_lang_file_list,
                                            range_cpus[i][0], range_cpus[i][1],
                                            seq_dir): i for i in range(len(range_cpus))}

            # Process the results as they become available
            for future in concurrent.futures.as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    result = future.result()
                    if result == 0:
                        pass
                    else:
                        print("failed")
                except Exception as e:
                    print(f"Task {task_id} generated an exception: {e}")

if __name__ == "__main__":
    main()