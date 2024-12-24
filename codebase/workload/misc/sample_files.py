'''
Sample files from input directory.
'''

import os
import sys
import glob
import shutil
import argparse
import random
from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--num_samples", '-n', type=int,
                        required=True,
                        help="The number of output samples.")
    parser.add_argument("--input_path", '-i', type=str,
                        required=True,
                        help="The input. It could be (a) a path to a directory; (b) a regex path supportted by glob. For case (a) and (b), all matched files will be tested.")
    parser.add_argument("--output_dir", '-o', type=str,
                        required=True,
                        help="The output directory.")
    parser.add_argument("--seed", '-s', type=int,
                        required=False, default=0x1234abcd,
                        help="The seed for randomly sampleing files.")


    args = parser.parse_args()
    print(args)

    if not os.path.isdir(args.output_dir):
        os.mkdir(args.output_dir)

    return args

def main(args):
    num_samples = args.num_samples
    input_path = args.input_path
    output_dir = args.output_dir
    seed = args.seed

    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    fpath_list = []
    if os.path.isdir(input_path):
        for fpath in glob.glob(input_path + "/*"):
            if os.path.isfile(fpath):
                fpath_list.append(fpath)
    else:
        for fpath in glob.glob(input_path):
            if os.path.isfile(fpath):
                fpath_list.append(fpath)

    if len(fpath_list) <= num_samples:
        print(f"The number of files in {input_path} is {len(fpath_list)}, which is <= the required sample number {num_samples}")
    else:
        random.seed(seed)
        fpath_list = random.sample(fpath_list, num_samples)

        for fpath in tqdm(fpath_list):
            shutil.copy(fpath, output_dir)

if __name__ == "__main__":
    args = parse_args()
    main(args)
