import os
import sys
import argparse
import glob
from collections import Counter
from prettytable import PrettyTable
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_phoney import EnvPhoney
from scripts.trace_proc.trace_split.split_op_mgr import OpTraceEntry
import scripts.executor.guest_side.generate_crash_image as crashimage
from scripts.crash_plan.crash_plan_type import CrashPlanType
import scripts.utils.utils as my_utils
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.vm_comm.memcached_wrapper import setup_memcached_client

def parse_args():
    parser = argparse.ArgumentParser(description='my args')
    parser.add_argument("--input", '-i', type=str, nargs='+',
                        required=True,
                        help="The input time logs. The argument could be a list of paths to a file, paths to a directory, and regex paths supportted by glob.")
    parser.add_argument("--output_dir", '-o', type=str,
                        required=True,
                        help="The output directory to store the result.")

    args = parser.parse_args()
    return args

def print_int_list_distribution(ll : list):
    print(str(Counter(ll)))

def print_elapsed_time_dict_as_table(elapsed_time_map):
    # Create a PrettyTable object
    table = PrettyTable()

    # Add columns to the table
    table.field_names = ["Function Name", "# of Calls", "Sum (seconds)", "Avg (seconds)"]

    for key, value in elapsed_time_map.items():
        table.add_row([key, len(value), f'{sum(value):,.6f}', f'{sum(value)/len(value):,.6f}'])

    table.align["Function Name"] = "l"
    table.align["# of Calls"] = "r"
    table.align["Sum (seconds)"] = "r"
    table.align["Avg (seconds)"] = "r"

    # Print the table
    print(table)

def dump_elapsed_time_dict_as_table(elapsed_time_map, output_dir):
    # Create a PrettyTable object
    table = PrettyTable()

    # Add columns to the table
    table.field_names = ["Function Name", "# of Calls", "Sum (seconds)", "Avg (seconds)"]

    for key, value in elapsed_time_map.items():
        table.add_row([key, len(value), f'{sum(value):,.6f}', f'{sum(value)/len(value):,.6f}'])

    table.align["Function Name"] = "l"
    table.align["# of Calls"] = "r"
    table.align["Sum (seconds)"] = "r"
    table.align["Avg (seconds)"] = "r"

    fpath = f'{output_dir}/result_time.txt'
    with open(fpath, 'w') as fd:
        fd.write(str(table))

def get_elapsed_time_title(line : str) -> str:
    title = line[line.find('elapsed_time'):]
    title = title.split(':')[0]
    title = title[len('elapsed_time.'):]
    return title

def get_elapsed_time_time(line : str) -> float:
    time = float(line.split(':')[-1])
    return time

def brief_time_in_one_file(fpath, elapsed_time_map) -> dict:
    print(f"read {fpath}")
    with open(fpath, 'r') as fd:
        for line in fd:
            line = line.strip()
            if 'elapsed_time.' in line:
                title = get_elapsed_time_title(line)
                time = get_elapsed_time_time(line)
                if title not in elapsed_time_map:
                    elapsed_time_map[title] = []
                elapsed_time_map[title].append(time)
    return elapsed_time_map

def main(args):
    input_files = args.input
    output_dir = args.output_dir
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    elapsed_time_map = dict()
    for path in input_files:
        if os.path.isfile(path):
            elapsed_time_map = brief_time_in_one_file(path, elapsed_time_map)
        elif os.path.isdir(path):
            for fpath in glob.glob(path + "/*"):
                if os.path.isfile(fpath):
                    elapsed_time_map = brief_time_in_one_file(fpath, elapsed_time_map)
        else:
            for fpath in glob.glob(path):
                if os.path.isfile(fpath):
                    elapsed_time_map = brief_time_in_one_file(fpath, elapsed_time_map)

    dump_elapsed_time_dict_as_table(elapsed_time_map, output_dir)

if __name__ == "__main__":
    args = parse_args()
    main(args)
