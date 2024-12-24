import sys
import os
import glob
import shutil
import random
from copy import copy
from tqdm import tqdm

def isFuncCallLine(line):
    if line.startswith('open') or \
            line.startswith('link') or \
            line.startswith('mkdir') or \
            line.startswith('rmdir') or \
            line.startswith('unlink') or \
            line.startswith('remove') or \
            line.startswith('dwrite') or \
            line.startswith('write') or \
            line.startswith('rename') or \
            line.startswith('symlink') or \
            line.startswith('truncate') or \
            line.startswith('falloc'):
        return True
    return False

def checkMarkAndChkpt(lines):
    # 0. remove all local_checkpoint, mark, and checkpoint 0
    lines = [line for line in lines if not line.startswith('local_checkpoint')]
    lines = [line for line in lines if not line.startswith('mark')]
    lines = [line for line in lines if not line.startswith('checkpoint 0')]

    # 1. add local_checkpoint
    for lno in range(len(lines)):
        line = lines[lno]
        if line.startswith('# declare'):
            if lno + 1 < len(lines) and not lines[lno + 1].startswith('local_checkpoint'):
                lines.insert(lno + 1, 'local_checkpoint\n')
            break

    # 2. add mark
    if not any('mark' in x for x in lines):
        for lno in range(len(lines)-1, 0, -1):
            line = lines[lno]
            if isFuncCallLine(line):
                lines.insert(lno, 'mark\n')
                break

    # 3. add checkpoint 0
    found_mark = False
    if not any('checkpoint 0' in x for x in lines):
        for lno in range(len(lines)):
            line = lines[lno]
            if found_mark and isFuncCallLine(line):
                lines.insert(lno+1, "checkpoint 0\n")
                break
            if line.startswith('mark'):
                found_mark = True

    return lines

def process(j_lang_file_list, j_file_dir):
    for j_file in tqdm(j_lang_file_list):
        jpath = j_file_dir + "/" + j_file

        fd = open(jpath, 'r')
        lines = fd.readlines()
        fd.close()

        # print(lines)
        new_lines = checkMarkAndChkpt(lines)
        # print(new_lines)

        with open(jpath, 'w') as fd:
            fd.writelines(new_lines)

def main():
    if len(sys.argv) != 2:
        print("usage: python3 this_script.py seq_dir")
        exit(0)

    j_file_dir = sys.argv[1] + "/j-lang-files/"

    j_lang_file_list = [f for f in os.listdir(j_file_dir) if os.path.isfile(os.path.join(j_file_dir, f))]
    # print(j_lang_file_list)

    process(j_lang_file_list, j_file_dir)

if __name__ == "__main__":
    main()