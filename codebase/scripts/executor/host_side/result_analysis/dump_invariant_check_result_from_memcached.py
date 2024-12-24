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
from scripts.executor.guest_side.deduce_mech import InvariantCheckErrorTypes
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
    for tp in InvariantCheckErrorTypes:
        count = 0
        rst_dict[tp] = []
        while True:
            count += 1
            key = f'InvariantCheckErrorTypes.{tp.value}.{count}'
            value = memcached_client.get(key)
            if value == None:
                break
            rst_dict[tp].append(value)
        print(f'{tp.value}: {count-1}')
    return rst_dict

def dump_rst(output_dir, tp : InvariantCheckErrorTypes, rst_list : list):
    output_dir = f'{output_dir}/{tp.value}'
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    for [report_time, basename, op_name_list, err_list, other_msg] in rst_list:
        fname = f'{output_dir}/{basename}-{len(op_name_list)}.txt'
        with open(fname, 'w') as fd:
            fd.write('#### report time: ' + report_time + '\n\n')
            fd.write('#### basename:\n' + basename + '\n\n')
            fd.write('#### op_name_list:\n' + str(op_name_list) + '\n\n')
            fd.write('#### err_list:\n' + "\n".join([str(x) for x in err_list]) + '\n\n')
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
