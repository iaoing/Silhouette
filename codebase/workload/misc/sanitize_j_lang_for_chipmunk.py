'''
Sanitize j-lang files for Chipmunk.
1. Add checkpoint declaration in '# declare'.
2. Add 'checkpoint 0' after the marked operation.
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
from tqdm import tqdm

JLangOps = [
    'write',
    'creat',
    'umount',
    'mkdir',
    'falloc',
    'link',
    'unlink',
    'rename',
    'truncate',
    'symlink',
    'rmdir',
    'remove',
    'dwrite',
    'open'
]

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--j_file_dir", '-j', type=str,
                        required=True,
                        help="The dir that stores j-lang files. Note this is an in-place modification. The j-lang file in this directory that contains the symlink operation will be deleted.")
    parser.add_argument("--num_thd", '-n', type=int,
                        required=False, default=1,
                        help="The number of threads.")

    args = parser.parse_args()
    print(args)

    if not os.path.isdir(args.j_file_dir):
        print("test file does not exist")
        exit(0)

    return args

def sanitize_j_file(thd_id, j_file_dir, j_lang_file_list, lo, hi):
    for idx in tqdm(range(lo, hi), desc=f"thd: {thd_id}"):
        jfile = j_file_dir + "/" + j_lang_file_list[idx]
        flag = False

        fd = open(jfile, 'r')
        lines = fd.readlines()
        fd.close()

        new_lines = []
        marked = False
        for line in lines:
            new_lines.append(line)
            if line.startswith('# declare'):
                new_lines.append('local_checkpoint\n')
            elif line.startswith('mark'):
                marked = True
            elif marked and line.split(' ')[0] in JLangOps:
                new_lines.append('checkpoint 0\n')

        fd = open(jfile, 'w')
        fd.writelines(new_lines)
        fd.close()

    return 0

def main(args):
    j_file_dir = args.j_file_dir
    num_thd = args.num_thd

    if not os.path.isdir(j_file_dir):
        print("test file does not exist")
        exit(0)

    max_cpus = multiprocessing.cpu_count()
    if num_thd == 0 or num_thd >= max_cpus:
        num_thd = max_cpus - 1

    j_lang_file_list = [f for f in os.listdir(j_file_dir) if os.path.isfile(os.path.join(j_file_dir, f))]

    cpus = num_thd
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
        future_to_task = {executor.submit(sanitize_j_file, i, j_file_dir, j_lang_file_list,
                                          range_cpus[i][0], range_cpus[i][1]): i for i in range(len(range_cpus))}

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
    main(args)
