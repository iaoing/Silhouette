'''
Insert snapshot operations into j-lang files.
This is used for testing NOVA's snapshot operations.
'''
import os
import sys
import glob
import argparse
import shutil, errno
import re
import subprocess
import concurrent.futures
import multiprocessing


OperationSet = ['creat', 'mkdir', 'falloc', 'write', 'dwrite', 'link', 'unlink', 'remove', 'rename', 'truncate', 'mmapwrite', 'symlink', 'rmdir']

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--input_dir", '-i', type=str,
                        required=True,
                        help="The input seq workload directory (e.g., workload/seq1)")
    parser.add_argument("--output_dir", '-o', type=str,
                        required=True,
                        help="The output directory (e.g., workload/seq1-snapshot)")
    parser.add_argument("--procfs_create_path", '-c', type=str,
                        required=True,
                        help="Procfs path to create a snapshot.")
    parser.add_argument("--procfs_delete_path", '-d', type=str,
                        required=True,
                        help="Procfs path to delete a snapshot.")
    parser.add_argument('--cpus', '-n', default=1, required=True, type=int,
                        help='Number of cpus to use')


    args = parser.parse_args()
    print(args)

    if not os.path.isdir(args.input_dir):
        print("No such input dir: %s" % (args.input_dir))
        exit(0)

    if not os.path.isdir(args.output_dir):
        os.mkdir(args.output_dir)

    max_cpus = multiprocessing.cpu_count()
    if args.cpus == 0 or args.cpus >= max_cpus:
        args.cpus = max_cpus - 1

    return args


def insert_create_snapshots(ori_lines, procfs_path):
    # return the new lines and the number of inserted create snapshots
    create_snapshot_str = "createSnapshot %s\n" % (procfs_path)
    to_insert_idx = []
    for i in range(len(ori_lines)):
        line = ori_lines[i]
        if not line or len(line) == 0:
            continue
        line = line.rstrip()
        lst = line.split(' ')
        if lst[0] == 'mark':
            to_insert_idx.append(i)

    to_insert_idx.sort(reverse=True)
    for idx in to_insert_idx:
        ori_lines.insert(idx, create_snapshot_str)

    return ori_lines, len(to_insert_idx)

def insert_delete_snapshots(ori_lines, procfs_path, num_snapshots):
    # return the new lines and the number of inserted delete snapshots
    to_insert_idx = []
    for i in range(len(ori_lines)):
        line = ori_lines[i]
        if not line or len(line) == 0:
            continue
        lst = line.split(' ')
        if lst[0] == 'checkpoint':
            to_insert_idx.append(i)

    num_inserted = 0
    for idx in to_insert_idx:
        if num_inserted >= num_snapshots:
            break
        delete_snapshot_str = "deleteSnapshot %s %d\n" % (procfs_path, num_inserted)
        ori_lines.insert(idx + num_inserted, delete_snapshot_str)
        num_inserted += 1

    while num_inserted < num_snapshots:
        delete_snapshot_str = "deleteSnapshot %s %d\n" % (procfs_path, num_inserted)
        ori_lines.append(delete_snapshot_str)
        num_inserted += 1

    return ori_lines

def snapshot_it(j_lang_file, procfs_create_path, procfs_delete_path):
    fd = open(j_lang_file, 'r')
    lines = fd.readlines()
    fd.close()

    lines, num_snapshots = insert_create_snapshots(lines, procfs_create_path)

    lines = insert_delete_snapshots(lines, procfs_delete_path, num_snapshots)

    with open(j_lang_file, 'w') as fd:
        for line in lines:
            fd.write(line)

def snapshotOneJFile(thread_id, j_lang_dir, j_lang_file_list, lower_idx, upper_idx,
                     procfs_create_path, procfs_delete_path):
    percent_1_span = (upper_idx - lower_idx) // 100
    for idx in range(lower_idx, upper_idx):
        if idx == lower_idx + percent_1_span * 10:
            print("thread: %d: completed 10%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 20:
            print("thread: %d: completed 20%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 30:
            print("thread: %d: completed 30%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 40:
            print("thread: %d: completed 40%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 50:
            print("thread: %d: completed 50%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 60:
            print("thread: %d: completed 60%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 70:
            print("thread: %d: completed 70%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 80:
            print("thread: %d: completed 80%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 90:
            print("thread: %d: completed 90%\n" % (thread_id))
        elif idx == lower_idx + percent_1_span * 100:
            print("thread: %d: completed 100%\n" % (thread_id))

        j_lang_file = j_lang_dir + "/" + j_lang_file_list[idx]
        snapshot_it(j_lang_file, procfs_create_path, procfs_delete_path)
    return 0

def main(input_dir, output_dir, procfs_create_path, procfs_delete_path, cpus):
    # copy then do it in-place
    shutil.copy(input_dir + "/base.cpp", output_dir)
    shutil.copy(input_dir + "/base-j-lang", output_dir)
    shutil.copy(input_dir + "/Makefile", output_dir)
    shutil.copytree(input_dir + "/j-lang-files", output_dir + "/j-lang-files", dirs_exist_ok=True)

    j_lang_dir = "%s/j-lang-files" % (output_dir)
    j_lang_file_list = [f for f in os.listdir(j_lang_dir) if os.path.isfile(os.path.join(j_lang_dir, f))]
    print(j_lang_file_list)
    print(len(j_lang_file_list))

    files_per_cpu = len(j_lang_file_list)//cpus
    range_cpus = []
    for i in range(cpus):
        # one cpu runs on [lower_idx, upper_idx)
        lower_idx = i * files_per_cpu + 1
        upper_idx = (i + 1) * files_per_cpu + 1
        if i == 0:
            lower_idx = 0
        if i + 1 == cpus:
            upper_idx = len(j_lang_file_list)
        range_cpus.append([lower_idx, upper_idx])

    print(range_cpus)
    with concurrent.futures.ThreadPoolExecutor(max_workers=cpus) as executor:
        # Submit tasks to the thread pool
        future_to_task = {executor.submit(snapshotOneJFile, i, j_lang_dir, j_lang_file_list,
                                          range_cpus[i][0], range_cpus[i][1],
                                          procfs_create_path, procfs_delete_path): i for i in range(len(range_cpus))}

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
    args = parse_args()
    main(args.input_dir, args.output_dir, args.procfs_create_path, args.procfs_delete_path, args.cpus)