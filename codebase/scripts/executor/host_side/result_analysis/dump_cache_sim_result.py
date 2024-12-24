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
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.vm_comm.memcached_wrapper import setup_memcached_client

def parse_args():
    parser = argparse.ArgumentParser(description='my args')
    parser.add_argument("--output_dir", '-o', type=str,
                        required=True,
                        help="The output directory to store the result.")

    args = parser.parse_args()
    return args

def get_cache_sim_result_count_from_mc(memcached_client):
    key = 'cache_sim_result_count'
    num = mc_wrapper.mc_get_wrapper(memcached_client, key)
    return num

def dump_cache_sim_result(memcached_client, output_dir):
    max_count = get_cache_sim_result_count_from_mc(memcached_client)
    if not max_count:
        print("No cache simulation result in Memcached.")
        return

    idx = -1
    while idx <= max_count:
        idx += 1
        key = f'cache_sim_result.{idx}'
        value = memcached_client.get(key)
        if value == None:
            continue
        report_time = value[0]
        value = value[1:]
        basename : str = value[0]
        op_name_list : list = value[1]
        # lists of in-flight stores' sequences
        in_flight_store_num : list = value[2]
        # number of crash plan dict
        # the key is the fence seq
        # the value is a tuple: {num of crash plans, number of in-flight stores, num of computed in flight stores}
        num_cps_map : dict = value[3]
        # a list of TraceEntry that are memcpy
        mem_copy_list : list = value[4]
        # a list of TraceEntry that are memset
        mem_set_list : list = value[5]
        # a list of atomic flush ops
        dup_flushes : list = value[6]
        # a list of atomic fence ops
        dup_fences : list = value[7]
        # a list of atomic store ops
        unflushed_stores : list = value[8]

        data = ''
        data += f'report_time: {report_time}\n\n'
        data += str(basename) + "\n\n"
        data += 'op_name_list: ' + str(op_name_list) + "\n\n"
        data += 'in_flight_store_num:\n' + str(in_flight_store_num) + "\n\n"
        data += 'num_cps_map:\n' + str(num_cps_map) + "\n\n"
        data += 'mem_copy_list:\n' + str(mem_copy_list) + "\n\n"
        data += 'mem_set_list:\n' + str(mem_set_list) + "\n\n"
        data += 'dup_flushes:\n' + str(dup_flushes) + "\n\n"
        data += 'dup_fences:\n' + str(dup_fences) + "\n\n"
        data += 'unflushed_stores:\n' + str(unflushed_stores) + "\n\n"

        fpath = f"{output_dir}/{basename}-{len(op_name_list)}-{op_name_list[-1]}-cache-sim.txt"
        with open(fpath, 'w') as fd:
            fd.write(data)

def main(args):
    output_dir = args.output_dir
    my_utils.mkdirDirs(output_dir, exist_ok=True)

    env = EnvPhoney()
    memcached_client = setup_memcached_client(env.MEMCACHED_IP_ADDRESS_HOST(), env.MEMCACHED_PORT(), 'result_analysis')

    dump_cache_sim_result(memcached_client, output_dir)

if __name__ == "__main__":
    args = parse_args()
    main(args)
