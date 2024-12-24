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
from scripts.crash_plan.crash_plan_type import CrashPlanType
import scripts.utils.utils as my_utils
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
    for tp in CrashPlanType:
        key = f'CrashPlanType.{tp.value}.count'
        count = memcached_client.get(key)
        if count != None:
            rst_dict[tp] = count
    return rst_dict

def main(args):
    output_dir = args.output_dir
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    env = EnvPhoney()
    memcached_client = setup_memcached_client(env.MEMCACHED_IP_ADDRESS_HOST(), env.MEMCACHED_PORT(), 'result_analysis')

    rst_dict = iterate_result(memcached_client)

    data = ''
    for tp, count in rst_dict.items():
        data += f'CrashPlanType.{tp.value}: {count}\n'

    with open(f"{output_dir}/result.txt", 'w') as fd:
        fd.write(data)

if __name__ == "__main__":
    args = parse_args()
    main(args)
