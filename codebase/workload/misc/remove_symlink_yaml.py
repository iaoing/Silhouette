'''
Remove yaml files that contain the symlink operation.
Yaml files are used by Vinter. Using this script to filter out all symlink operations, allowing a fair comparison between Silhouette, Chipmunk, and Vinter.
This is used to filter out the operations (symlink) that Chipmunk cannot process.
Chipmunk cannot handle it:
https://github.com/utsaslab/chipmunk/blob/87619232e1703f988366400fe8f1151a0421ea54/chipmunk/executor/ace/ace.py#L834-L841
https://github.com/utsaslab/chipmunk/blob/87619232e1703f988366400fe8f1151a0421ea54/chipmunk/executor/harness/Tester.cpp#L1410-L1413
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

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--yaml_file_dir", '-j', type=str,
                        required=True,
                        help="The dir that stores j-lang files. Note this is an in-place modification. The j-lang file in this directory that contains the symlink operation will be deleted.")
    parser.add_argument("--num_thd", '-n', type=int,
                        required=False, default=1,
                        help="The number of threads.")

    args = parser.parse_args()
    print(args)

    if not os.path.isdir(args.yaml_file_dir):
        print("test file does not exist")
        exit(0)

    return args

def removeSymlinkJFile(thd_id, yaml_file_dir, yaml_file_list, lo, hi):
    for idx in tqdm(range(lo, hi), desc=f"thd: {thd_id}"):
        yaml_file = yaml_file_dir + "/" + yaml_file_list[idx]
        flag = False

        fd = open(yaml_file, 'r')
        lines = fd.readlines()
        fd.close()

        for line in lines:
            if 'ln -s' in line:
                flag = True
                break

        if flag:
            # print(f"remove {yaml_file}", file=sys.stderr)
            os.remove(yaml_file)

    return 0

def main(args):
    yaml_file_dir = args.yaml_file_dir
    num_thd = args.num_thd

    if not os.path.isdir(yaml_file_dir):
        print("test file does not exist")
        exit(0)

    max_cpus = multiprocessing.cpu_count()
    if num_thd == 0 or num_thd >= max_cpus:
        num_thd = max_cpus - 1

    yaml_file_list = [f for f in os.listdir(yaml_file_dir) if os.path.isfile(os.path.join(yaml_file_dir, f))]

    cpus = num_thd
    files_per_cpu = len(yaml_file_list)//cpus
    range_cpus = []
    for i in range(cpus):
        # one cpu runs on [lower_idx, upper_idx)
        lower_idx = i * files_per_cpu + 1
        upper_idx = (i + 1) * files_per_cpu + 1
        if i == 0:
            lower_idx = 0
        if i + 1 == cpus:
            upper_idx = len(yaml_file_list)
        range_cpus.append([lower_idx, upper_idx])

    print(range_cpus)
    with concurrent.futures.ThreadPoolExecutor(max_workers=cpus) as executor:
        # Submit tasks to the thread pool
        future_to_task = {executor.submit(removeSymlinkJFile, i, yaml_file_dir, yaml_file_list,
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
