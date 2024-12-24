import os
import sys
from pymemcache.client.base import PooledClient
import time

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

import scripts.utils.logger as log
from scripts.vm_comm.heartbeat_host import check_heartbeat_local
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
from scripts.vm_comm.memcached_wrapper import mc_set_wrapper, setup_memcached_pooled_client

def main():
    log.setup_global_logger(stm=sys.stderr, stm_lv=10)

    # memcached_client = PooledClient(('127.0.0.1', 11211))
    memcached_client = setup_memcached_pooled_client('127.0.0.1', 11211)

    key = 'hearbeat_test'
    mc_set_wrapper(memcached_client, key, 1)
    start_heartbeat_service(memcached_client, key)

    n_seconds = None
    curr_time = None
    check_flag = False
    n_checks = 10
    while n_checks > 0:
        time.sleep(5)
        check_flag, n_seconds, curr_time = check_heartbeat_local(memcached_client, key, n_seconds, curr_time)
        if not check_flag:
            stop_heartbeat_service()
            assert False, "Test failed: invalid heartbeat msg"
        n_checks -= 1

    stop_heartbeat_service()

if __name__ == "__main__":
    main()
