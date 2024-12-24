'''
Sample files from input directory.
'''

import os
import sys
import glob
import shutil
import argparse
import re
import random
from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--input_path", '-i', type=str,
                        required=True,
                        help="The input. It could be (a) a path to a directory; (b) a regex path supportted by glob. For case (a) and (b), all matched files will be tested.")
    parser.add_argument("--output_file", '-o', type=str,
                        required=True,
                        help="The output file to store the list of shuffled files.")
    parser.add_argument("--seed", '-s', type=int,
                        required=False, default=0x1234abcd,
                        help="The seed for randomly sampleing files.")


    args = parser.parse_args()
    print(args)

    return args

def main(args):
    input_path = args.input_path
    output_file = args.output_file
    seed = args.seed

    fname_list = []
    if os.path.isdir(input_path):
        for fpath in glob.glob(input_path + "/*"):
            if os.path.isfile(fpath):
                fname_list.append(os.path.basename(fpath))
    else:
        for fpath in glob.glob(input_path):
            if os.path.isfile(fpath):
                fname_list.append(os.path.basename(fpath))



    # sort by the first number in the filename, then shuffle
    def extract_first_int(basename):
            match = re.search(r'\d+', basename)
            return int(match.group()) if match else 0

    fname_list.sort(key=extract_first_int, reverse=False)

    random.seed(seed)
    random.shuffle(fname_list)

    data = ''
    for fname in tqdm(fname_list):
        data += f'{fname}\n'

    with open(output_file, 'w') as fd:
        fd.write(data)

if __name__ == "__main__":
    args = parse_args()
    main(args)
