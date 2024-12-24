import os
import sys
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
import time

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

import scripts.utils.logger as log
from scripts.vm_comm.heartbeat_host import check_heartbeat
from scripts.vm_comm.memcached_wrapper import custom_raw_set, setup_memcached_pooled_client

def main():
    log.setup_global_logger(stm=sys.stderr, stm_lv=10)
    memcached_client : CMPooledClient = setup_memcached_pooled_client('127.0.0.1', 11211)

    key = 'test_custom_raw_set'
    value = '333'

    custom_raw_set(memcached_client, key, value)
    print(f"set key-value pair: {key}, {value}")

    retrieved_value = memcached_client.get(key)
    print(f"retrieved value: {retrieved_value}")

    memcached_client.close()

if __name__ == "__main__":
    main()
