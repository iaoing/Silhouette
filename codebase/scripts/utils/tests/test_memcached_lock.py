import os
import re
import sys
import stat
import subprocess
import argparse
import time
import traceback
import itertools
from shutil import copyfile
import concurrent.futures
import multiprocessing
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

import scripts.vm_comm.memcached_lock as mc_lock

glo_count = 0

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"elapsed_time.guest.memcached_cas.{func.__name__}:{time.perf_counter() - start_time}")
        return result
    return wrapper

def init_lock(memcached_client, key):
    return memcached_client.set(key, False)

def acquire_lock(memcached_client, key):
    while True:
        value, cas_id = memcached_client.gets(key)
        if value == True:
            # someone hold this lock
            time.sleep(0.005)
            continue
        elif memcached_client.cas(key, True, cas_id):
            break
        else:
            # someone cas-ed this lock before this one
            time.sleep(0.005)
            continue
    return True

def release_lock(memcached_client, key):
    while True:
        value, cas_id = memcached_client.gets(key)
        if value == False:
            print("the lock is False", file=sys.stderr)
            # some bad thing happened
            # what should we do?
            break
        if memcached_client.cas(key, False, cas_id):
            break
    return True

class MemcachedMutex:
    # too time-consuming, do not why.
    def __init__(self, client, key, expire=0):
        self.client = client
        self.key = key
        self.expire = expire

    def acquire(self):
        while True:
            # Try to add the key to Memcached with an expiration time
            if self.client.add(self.key, 'locked', expire=0, noreply=False):
                return True
            time.sleep(0.01)  # Wait a bit before retrying

    def release(self):
        self.client.delete(self.key)

def cas_proc(pid, mc : CMPooledClient, num_cas_per_proc):
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        while True:
            k, cas_id = mc.gets('k')
            if mc.cas('k', k+1, cas_id):
                break
            else:
                time.sleep(0.005)
    print(f"elapsed_time.guest.memcached_cas.cas_proc:{time.perf_counter() - start_time} seconds")
    return 0

def set_proc_1(pid, mc : CMPooledClient, num_cas_per_proc):
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        k = mc.get('k')
        mc.set('k', k+1)
    print(f"elapsed_time.guest.memcached_cas.set_proc_1:{time.perf_counter() - start_time} seconds")
    return 0

def set_proc_2(pid, mc : CMPooledClient, num_cas_per_proc):
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        mc.set(f'{i+pid*num_cas_per_proc}', i+pid*num_cas_per_proc)
    print(f"elapsed_time.guest.memcached_cas.set_proc_2:{time.perf_counter() - start_time} seconds")
    return 0

def incr_proc(pid, mc : CMPooledClient, num_cas_per_proc):
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        mc.incr('k', 1)
    print(f"elapsed_time.guest.memcached_cas.incr_proc:{time.perf_counter() - start_time} seconds")
    return 0

def lock_proc_1(pid, mc : CMPooledClient, num_cas_per_proc):
    global glo_count
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        acquire_lock(mc, "test_memcached_lock")
        # mutex is thread-safe, but the get and set are not safe
        glo_count += 1
        # why gets/cas version is faster than the get/set version?
        # maybe because of the LRU in memcached
        k = mc.get('k')
        mc.set('k', k+1)
        # while True:
        #     k, cas = mc.gets('k')
        #     if mc.cas('k', k+1, cas):
        #         break
        release_lock(mc, "test_memcached_lock")
    print(f"elapsed_time.guest.memcached_cas.lock_proc_1:{time.perf_counter() - start_time} seconds")
    return 0

def lock_proc_2(pid, mc : CMPooledClient, num_cas_per_proc):
    global glo_count
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        acquire_lock(mc, "test_memcached_lock")
        # mutex is thread-safe, but the get and set are not safe
        glo_count += 1
        k = mc.get('k')
        mc.set('k', k+1)
        release_lock(mc, "test_memcached_lock")
    print(f"elapsed_time.guest.memcached_cas.lock_proc_2:{time.perf_counter() - start_time} seconds")
    return 0

def lock_proc_3(pid, mc : CMPooledClient, num_cas_per_proc):
    global glo_count
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        acquire_lock(mc, "test_memcached_lock")
        # mutex is thread-safe, but the get and set are not safe
        glo_count += 1
        # why gets/cas version is faster than the get/set version?
        # k = mc.get('k')
        # mc.set('k', k+1)
        while True:
            k, cas = mc.gets('k')
            if mc.cas('k', k+1, cas):
                break
        release_lock(mc, "test_memcached_lock")
    print(f"elapsed_time.guest.memcached_cas.lock_proc_3:{time.perf_counter() - start_time} seconds")
    return 0

def lock_proc_4(pid, mc : CMPooledClient, mutex : MemcachedMutex, num_cas_per_proc):
    global glo_count
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        mutex.acquire()
        # mutex is thread-safe, but the get and set are not safe
        glo_count += 1
        k = mc.get('k')
        mc.set('k', k+1)
        mutex.release()
    print(f"elapsed_time.guest.memcached_cas.lock_proc_4:{time.perf_counter() - start_time} seconds")
    return 0

def lock_proc_5(pid, mc : CMPooledClient, mutex : MemcachedMutex, num_cas_per_proc):
    global glo_count
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        mutex.acquire()
        # mutex is thread-safe, but the get and set are not safe
        glo_count += 1
        # k = mc.get('k')
        # mc.set('k', k+1)
        # while True:
        #     k, cas = mc.gets('k')
        #     if mc.cas('k', k+1, cas):
        #         break
        #     else:
        #         time.sleep(0.005)
        mutex.release()
    print(f"elapsed_time.guest.memcached_cas.lock_proc_5:{time.perf_counter() - start_time} seconds")
    return 0

def lock_proc_6(pid, mc : CMPooledClient, num_cas_per_proc):
    global glo_count
    start_time = time.perf_counter()
    milestones = range(0, num_cas_per_proc, num_cas_per_proc//10)
    for i in range(num_cas_per_proc):
        if i in milestones:
            print(f"#{pid} task: {100 * i // num_cas_per_proc}%, elapsed time: {time.perf_counter() - start_time} seconds")
        mc_lock.acquire_lock(mc, key='mc_lock_test')
        # mutex is thread-safe, but the get and set are not safe
        glo_count += 1
        while True:
            k, cas = mc.gets('k')
            if mc.cas('k', k+1, cas):
                break
        mc_lock.release_lock(mc, key='mc_lock_test')
    print(f"elapsed_time.guest.memcached_cas.lock_proc_6:{time.perf_counter() - start_time} seconds")
    return 0

@timeit
def main():
    global glo_count
    # mc = CMClient(('192.168.122.1', '11211'), serde=CMSerde.compressed_serde, connect_timeout=5, timeout=5)
    mc = CMPooledClient(('192.168.122.1', '11211'), serde=CMSerde.compressed_serde, connect_timeout=5, timeout=5, max_pool_size=1024)
    init_lock(mc, "test_memcached_lock")
    mutex = MemcachedMutex(mc, "test_mutex")
    mc_lock.init_lock(mc, key='mc_lock_test')
    mc.delete('k')
    mc.set('k', 0)
    num_proc = 10
    num_cas_per_proc = 10**2

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_proc) as executor:
        # Submit tasks to the thread pool
        # future_to_task = {executor.submit(incr_proc, i, mc, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(cas_proc, i, mc, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(set_proc_1, i, mc, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(set_proc_2, i, mc, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(lock_proc_1, i, mc, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(lock_proc_2, i, mc, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(lock_proc_3, i, mc, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(lock_proc_4, i, mc, mutex, num_cas_per_proc) : i for i in range(num_proc)}
        # future_to_task = {executor.submit(lock_proc_5, i, mc, mutex, num_cas_per_proc) : i for i in range(num_proc)}
        future_to_task = {executor.submit(lock_proc_6, i, mc, num_cas_per_proc) : i for i in range(num_proc)}

        # Process the results as they become available
        for future in concurrent.futures.as_completed(future_to_task):
            task_id = future_to_task[future]
            try:
                result = future.result()
                if result == 0:
                    print(f"Task #{task_id} passed.")
                else:
                    print(f"Task #{task_id} failed")
            except Exception as e:
                traceback.print_exc()
                print(f"Task #{task_id} generated an exception: {e.__class__.__name__,}: {e}")

    k = mc.get('k')
    print(f'glo_cout: {glo_count}, k: {k}, num_proc: {num_proc}, num_cas_per_proc: {num_cas_per_proc}')

if __name__ == "__main__":
    main()
