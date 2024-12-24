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
    rst_list = []
    count = 0
    while True:
        count += 1
        key = f'crash_plan_to_validate_rst.{count}'
        value = memcached_client.get(key)
        if value == None:
            break
        rst_list.append(value)
    return rst_list

def main(args):
    output_dir = args.output_dir
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    env = EnvPhoney()
    memcached_client = setup_memcached_client(env.MEMCACHED_IP_ADDRESS_HOST(), env.MEMCACHED_PORT(), 'result_analysis')

    rst_list = iterate_result(memcached_client)

    data = ''
    for value in rst_list:
        data += f'report time: {value[0]}\n'
        data += f'test case: {value[1]}\n'
        data += f'op name list: {value[2]}\n'
        data += f'op idx: {value[3]}\n'
        data += f'total cps: {value[4]}\n'
        data += f'cp idx: {value[5]}\n'
        data += f'validate result type: {value[6]}\n\n\n'

    with open(f"{output_dir}/result.txt", 'w') as fd:
        fd.write(data)

if __name__ == "__main__":
    args = parse_args()
    main(args)
