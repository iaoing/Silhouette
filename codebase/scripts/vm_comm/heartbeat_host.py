import os
import sys
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
import time
import threading
from datetime import datetime

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.const_var import HEARTBEAT_INTERVAL
from scripts.utils.utils import TIMEZONE_EST
import scripts.utils.logger as log

last_heartbeat_second = None
last_heartbeat_time = None

def check_heartbeat(memcached_client, key, timeout=HEARTBEAT_INTERVAL*2.2):
    global last_heartbeat_second, last_heartbeat_time
    value = 0 # in seconds

    value = memcached_client.get(key)
    curr_heartbeat_time = datetime.now(TIMEZONE_EST)

    msg = f"check_heartbeat: value: {value}, curr_heartbeat_time: {curr_heartbeat_time}, last_heartbeat_second: {last_heartbeat_second}, last_heartbeat_time: {value}"
    log.global_logger.debug(msg)

    if value == None:
        # guest has not set it yet
        return True, 0, curr_heartbeat_time

    if last_heartbeat_second == None and last_heartbeat_time == None:
        return True, value, curr_heartbeat_time

    if value > last_heartbeat_second:
        return True, value, curr_heartbeat_time
    else:
        time_interval = (curr_heartbeat_time - last_heartbeat_time).total_seconds()
        if time_interval <= timeout:
            # in case of network, allow 2 * interval deviation
            msg = f'last_heartbeat_second: {last_heartbeat_second}, last_heartbeat_time: {last_heartbeat_time}, value: {value}, curr_heartbeat_time: {curr_heartbeat_time}'
            log.global_logger.debug(msg)
            return True, value, curr_heartbeat_time
        else:
            msg = f'last_heartbeat_second: {last_heartbeat_second}, last_heartbeat_time: {last_heartbeat_time}, value: {value}, curr_heartbeat_time: {curr_heartbeat_time}'
            log.global_logger.error(msg)
            return False, value, curr_heartbeat_time

def check_heartbeat_local(memcached_client, key, local_last_heartbeat_second, local_last_heartbeat_time, timeout=HEARTBEAT_INTERVAL*2.2):
    value = 0 # in seconds

    value = memcached_client.get(key, 'NotFound')
    curr_heartbeat_time = datetime.now(TIMEZONE_EST)

    # 1 check per second
    # 4 msg is 1 KB
    # 1 min is 15 KB
    # 1 hour is 0.9 MB
    # 1 day is 21.1 MB
    # 1 week is 147 MB
    msg = f"check_heartbeat: key: {key}, value: {value}, curr_heartbeat_time: {curr_heartbeat_time}, local_last_heartbeat_second: {local_last_heartbeat_second}, local_last_heartbeat_time: {local_last_heartbeat_time}"
    log.global_logger.debug(msg)

    if value == None:
        # guest has not set it yet
        return True, 0, curr_heartbeat_time

    if local_last_heartbeat_second == None and local_last_heartbeat_time == None:
        return True, value, curr_heartbeat_time

    if value > local_last_heartbeat_second:
        return True, value, curr_heartbeat_time
    else:
        time_interval = (curr_heartbeat_time - local_last_heartbeat_time).total_seconds()
        if time_interval <= timeout:
            # in case of network, allow time interval deviation
            msg = f'local_last_heartbeat_second: {local_last_heartbeat_second}, local_last_heartbeat_time: {local_last_heartbeat_time}, value: {value}, curr_heartbeat_time: {curr_heartbeat_time}'
            log.global_logger.debug(msg)
            return True, local_last_heartbeat_second, local_last_heartbeat_time
        else:
            msg = f'local_last_heartbeat_second: {local_last_heartbeat_second}, local_last_heartbeat_time: {local_last_heartbeat_time}, value: {value}, curr_heartbeat_time: {curr_heartbeat_time}'
            log.global_logger.error(msg)
            return False, value, curr_heartbeat_time
