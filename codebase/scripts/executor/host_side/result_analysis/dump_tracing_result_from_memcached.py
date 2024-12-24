import os
import sys
import argparse
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_phoney import EnvPhoney
from scripts.trace_proc.trace_split.split_op_mgr import OpTraceEntry
import scripts.executor.guest_side.generate_crash_image as crashimage
import scripts.utils.utils as my_utils
from scripts.executor.guest_side.tracing import TracingRstType
from scripts.vm_comm.memcached_wrapper import setup_memcached_client

def parse_args():
    parser = argparse.ArgumentParser(description='my args')
    parser.add_argument("--output_dir", '-o', type=str,
                        required=True,
                        help="The output directory to store the result.")

    args = parser.parse_args()
    return args

def iterate_result(memcached_client) -> list:
    rst_dict = dict()
    for tp in TracingRstType:
        count = 0
        rst_dict[tp] = []
        while True:
            count += 1
            key = f'TracingRstType.{tp.value}.{count}'
            value = memcached_client.get(key)
            if value == None:
                break
            rst_dict[tp].append(value)
        print(f'{tp.value}: {count-1}')
    return rst_dict

def dump_rst(output_dir, tp : TracingRstType, rst_list : list):
    output_dir = f'{output_dir}/{tp.value}'
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    for [basename, other_msg] in rst_list:
        fname = f'{output_dir}/{basename}.txt'
        with open(fname, 'w') as fd:
            fd.write('#### basename:\n' + basename + '\n\n')
            fd.write('#### other_msg:\n' + str(other_msg) + '\n\n')

def main(args):
    output_dir = args.output_dir
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    env = EnvPhoney()
    memcached_client = setup_memcached_client(env.MEMCACHED_IP_ADDRESS_HOST(), env.MEMCACHED_PORT(), 'result_analysis')

    rst_dict = iterate_result(memcached_client)
    for tp, rst_list in rst_dict.items():
        if len(rst_list) > 0:
            dump_rst(output_dir, tp, rst_list)

if __name__ == "__main__":
    args = parse_args()
    main(args)
