import os
import sys
import time

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

import scripts.vm_comm.memcached_wrapper as mc_wrapper
import scripts.utils.logger as log

KEY_UNLOCKED = "UNLOCKED"
KEY_LOCKED = "LOCKED"

def init_lock(memcached_client, key):
    global KEY_UNLOCKED, KEY_LOCKED
    return mc_wrapper.mc_set_wrapper(memcached_client, key, KEY_UNLOCKED)

def acquire_lock(memcached_client, key, sleep_time=0.01):
    global KEY_UNLOCKED, KEY_LOCKED
    while True:
        value, cas_id = mc_wrapper.mc_gets_wrapper(memcached_client, key)
        if value == None:
            # the key does not exist
            return False
        elif value == KEY_LOCKED:
            # someone hold this lock
            # msg = "someone hold this lock"
            # log.global_logger.debug(msg)
            time.sleep(sleep_time)
            continue
        elif mc_wrapper.mc_cas_wrapper(memcached_client, key, KEY_LOCKED, cas_id):
            # successfully cas-ed
            return True
        else:
            # someone cas-ed this lock before this one
            # msg = "someone cas-ed this lock"
            # log.global_logger.debug(msg)
            time.sleep(sleep_time)
            continue
    return True

def release_lock(memcached_client, key):
    global KEY_UNLOCKED, KEY_LOCKED
    while True:
        value, cas_id = mc_wrapper.mc_gets_wrapper(memcached_client, key)
        if value == None:
            # some bad thing happened
            # what should we do?
            return False
        if mc_wrapper.mc_cas_wrapper(memcached_client, key, KEY_UNLOCKED, cas_id):
            break
    return True

class MemcachedMutex(object):
    def __init__(self, memcached_client, key):
        self.memcached_client = memcached_client
        self.key = key
        init_lock(self.memcached_client, self.key)

    def acquire(self, sleep_time=0.005):
        return acquire_lock(self.memcached_client, self.key, sleep_time)

    def release(self):
        return release_lock(self.memcached_client, self.key)
