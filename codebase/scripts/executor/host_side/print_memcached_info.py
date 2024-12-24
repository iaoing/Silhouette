import os
import sys
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase
from scripts.fs_conf.nova.env_nova import EnvNova
from scripts.executor.guest_side.validate_image import ValidateRstType

def print_failed_cases(memcached_client : CMClient):
    failed_case_count = 0
    while True:
        failed_case_count += 1
        key = f'failed_test_case.{failed_case_count}'
        value = memcached_client.get(key)
        if value == None:
            break
        print(f'key: {key}, value: {str(value)}')
    print()

def print_validate_type_info(memcached_client : CMClient):
    for tp in ValidateRstType:
        count = 0
        print(f"\n\n{tp}\n")
        while True:
            count += 1
            key = f'{tp.value}.{count}'
            value = memcached_client.get(key)
            if value == None:
                break
            print(f'key: {key}, value: {str(value)}')

def print_unique_cases(memcached_client : CMClient):
    unique_case_count = 0
    while True:
        unique_case_count += 1
        key = f'unique_fs_op.{unique_case_count}'
        value = memcached_client.get(key)
        if value == None:
            break
        print(f'key: {key}, value: {str(value)}')
    print()

def print_misc_kv(memcached_client, key):
    value = memcached_client.get(key)
    print(f'key: {key}, value: {str(value)}')

def print_id_seq_set(memcached_client):
    key = f'id_seq_set'
    id_seq_set = memcached_client.get(key)
    if id_seq_set == None:
        print(f'key: {key}, id_seq_set: {id_seq_set}')
    else:
        print(f'key: {key}, len of id_seq_set: {len(id_seq_set)}')

def print_vm_info(memcached_client, vm_id):
    key = f'heartbeat.{vm_id}'
    print_misc_kv(memcached_client, key)
    key = f'{vm_id}.state'
    print_misc_kv(memcached_client, key)
    key = f'{vm_id}.start'
    print_misc_kv(memcached_client, key)
    key = f'{vm_id}.unique_indices'
    print_misc_kv(memcached_client, key)
    key = f'{vm_id}.end'
    print_misc_kv(memcached_client, key)
    print('\n')

def print_cache_sim_result(memcached_client):
    idx = 0
    while True:
        key = f'cache_sim_result_{idx}'
        value = memcached_client.get(key)
        if value == None:
            break
        print(f"{key}\n\t{value}\n\n")
        idx += 1

def main():
    env : EnvBase = EnvNova()
    memcached_client = CMClient((env.MEMCACHED_IP_ADDRESS_HOST(), env.MEMCACHED_PORT()), serde=CMSerde.compressed_serde, connect_timeout=5, timeout=5)
    # print_failed_cases(memcached_client)
    # print_unique_cases(memcached_client)
    # print_cache_sim_result(memcached_client)
    # print_validate_type_info(memcached_client)
    print_misc_kv(memcached_client, 'next_exec_list_index')
    print_misc_kv(memcached_client, 'unique_case_count')
    print_misc_kv(memcached_client, 'failed_case_count')
    print_misc_kv(memcached_client, 'id_seq_set_lock')
    print_id_seq_set(memcached_client)

    key = 'vm_id_list'
    vm_id_list = memcached_client.get(key)
    print(f'\nvm_id_list: {vm_id_list}\n')
    if isinstance(vm_id_list, list):
        for vm_id in vm_id_list:
            print_vm_info(memcached_client, vm_id)

if __name__ == "__main__":
    main()
