import os
import sys
import argparse
import re
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
    parser.add_argument("--output_dir", '-o', type=str,
                        required=True,
                        help="The output directory to store the result.")

    args = parser.parse_args()
    return args

def get_count_from_mc(memcached_client):
    key = 'detailed_info_count'
    num = mc_wrapper.mc_get_wrapper(memcached_client, key)
    return num

def dump_cache_sim_result(memcached_client, output_dir):
    max_count = get_count_from_mc(memcached_client)
    if not max_count:
        print("No detailed info count in Memcached.")
        return

    idx = -1
    while idx <= max_count:
        idx += 1
        key = f'detailed_info.{idx}'
        value = memcached_client.get(key)
        if value == None:
            continue

        basename = 'unknown'
        op_idx = idx
        op_name_list = []
        if len(value) >= 3:
            basename = value[2]
        if len(value) >= 5:
            op_idx = value[3]
            op_name_list = value[4]

        fpath = f"{output_dir}/{basename}_{op_idx}_{op_name_list[-1]}.txt"
        with open(fpath, 'w') as fd:
            fd.write('#### report time: ' + value[0] + '\n\n')
            fd.write(value[1])

def main(args):
    output_dir = args.output_dir
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    env = EnvPhoney()
    memcached_client = setup_memcached_client(env.MEMCACHED_IP_ADDRESS_HOST(), env.MEMCACHED_PORT(), 'result_analysis')

    dump_cache_sim_result(memcached_client, output_dir)

if __name__ == "__main__":
    args = parse_args()
    main(args)
