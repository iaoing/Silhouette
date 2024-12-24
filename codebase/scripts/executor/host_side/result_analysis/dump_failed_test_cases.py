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

def get_count_from_mc(memcached_client, key):
    num = mc_wrapper.mc_get_wrapper(memcached_client, key)
    return num

def extract_first_int(value):
    basename = value[0]
    match = re.search(r'\d+', basename)
    return int(match.group()) if match else 0

def dump_cache_sim_result(memcached_client, output_dir, key1, key2):
    max_count = get_count_from_mc(memcached_client, key1)
    if not max_count:
        print(f"No {key1} in Memcached.")
        return

    idx = -1
    op_dict : dict = dict()

    fpath = f"{output_dir}/{key2}.txt"
    fd = open(fpath, 'w')

    while idx <= max_count:
        idx += 1
        key = f'{key2}.{idx}'
        basename = memcached_client.get(key)
        if basename == None:
            continue

        fd.write(basename + "\n")

    fd.close()

def main(args):
    output_dir = args.output_dir
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    env = EnvPhoney()
    memcached_client = setup_memcached_client(env.MEMCACHED_IP_ADDRESS_HOST(), env.MEMCACHED_PORT(), 'result_analysis')

    dump_cache_sim_result(memcached_client, output_dir, 'failed_case_count', 'failed_test_case')
    dump_cache_sim_result(memcached_client, output_dir, 'failed_ctx_case_count', 'failed_ctx_test_case')
    dump_cache_sim_result(memcached_client, output_dir, 'failed_umount_case_count', 'failed_umount_test_case')
    dump_cache_sim_result(memcached_client, output_dir, 'failed_syslog_case_count', 'failed_syslog_test_case')

if __name__ == "__main__":
    args = parse_args()
    main(args)
