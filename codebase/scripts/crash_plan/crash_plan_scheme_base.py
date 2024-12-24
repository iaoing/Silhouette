import os
import sys
import time
import pickle

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from scripts.crash_plan.crash_plan_entry import CrashPlanEntry
from scripts.crash_plan.crash_plan_type import CrashPlanType, CrashPlanSamplingType
import scripts.vm_comm.memcached_wrapper as mc_wrapper
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.scheme_base.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class CrashPlanSchemeBase():
    def __init__(self):
        # a list of generated crash plans
        self.cp_entry_list = []

    def generate_crash_plans(self):
        raise NotImplementedError("Method generate_crash_plans is not implemented.")

    @timeit
    def write_to_disk(self, dpath, file_prefix, use_pickle):
        for cp_idx in range(len(self.cp_entry_list)):
            cp : CrashPlanEntry = self.cp_entry_list[cp_idx]
            fpath = f'{dpath}/{file_prefix}-{cp_idx:02d}-{cp.type.value}.cp'
            if use_pickle:
                with open(fpath, 'wb') as fd:
                    pickle.dump(cp, fd)
            else:
                with open(fpath, 'w') as fd:
                    fd.write(str(cp))

    @timeit
    def send_to_memcached(self, memcached_client, existing_key):
        # we do not want to count crash plan multiple time after retesting a case
        if mc_wrapper.mc_add_wrapper(memcached_client, existing_key, '1'):
            for cp in self.cp_entry_list:
                cp : CrashPlanEntry

                key = f'CrashPlanType.{cp.type.value}.count'
                count = cp.num_cp_entries
                mc_wrapper.mc_incr_wrapper(memcached_client, key, count)
