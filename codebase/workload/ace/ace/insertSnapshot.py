'''
Insert snapshot operations into a j-lang files.
This is used for testing NOVA's snapshot operations.
'''
import os
import sys
import copy
import argparse


OperationSet = ['creat', 'mkdir', 'falloc', 'write', 'dwrite', 'link', 'unlink', 'remove', 'rename', 'truncate', 'mmapwrite', 'symlink', 'rmdir']

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--j_lang_file", '-j', type=str,
                        required=True,
                        help="J-lang file")
    parser.add_argument("--procfs_create_path", '-c', type=str,
                        required=True,
                        help="Procfs path to create a snapshot.")
    parser.add_argument("--procfs_delete_path", '-d', type=str,
                        required=True,
                        help="Procfs path to delete a snapshot.")
    parser.add_argument("--output_dir", '-o', type=str,
                        required=True,
                        help="The directory to save the generated j-lang with snapshot ops")


    args = parser.parse_args()
    print(args)

    if not os.path.isfile(args.j_lang_file):
        print("test file does not exist")
        exit(0)

    if not os.path.isdir(args.output_dir):
        os.mkdir(args.output_dir)

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

def main(j_lang_file, procfs_create_path, procfs_delete_path, output_dir):
    fd = open(j_lang_file, 'r')
    lines = fd.readlines()
    fd.close()

    lines, num_snapshots = insert_create_snapshots(lines, procfs_create_path)

    lines = insert_delete_snapshots(lines, procfs_delete_path, num_snapshots)

    fname = os.path.basename(j_lang_file)
    output_path = "%s/%s" % (output_dir, fname)
    with open(output_path, 'w') as fd:
        for line in lines:
            fd.write(line)


if __name__ == "__main__":
    args = parse_args()
    main(args.j_lang_file, args.procfs_create_path, args.procfs_delete_path, args.output_dir)