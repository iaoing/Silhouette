import os
import sys
import time
import random
import itertools
import copy
from functools import reduce

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from scripts.cache_sim.witcher.cache.witcher_cache import WitcherCache
from scripts.cache_sim.witcher.cache.reorder_simulator import ReorderSimulator
from scripts.cache_sim.witcher.binary_file.binary_file import EmptyBinaryFile
from scripts.cache_sim.witcher.cache.atomic_op import Fence, Store, Flush
from scripts.cache_sim.witcher.cache.entry_op_conv import convert_entry_list
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr, OpTraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.instid_srcloc_reader.instid_src_loc_reader import InstIdSrcLocReader
from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason, MechPMStoreEntry
from scripts.crash_plan.crash_plan_entry import CrashPlanEntry
from scripts.crash_plan.crash_plan_type import CrashPlanType, CrashPlanSamplingType
from scripts.crash_plan.crash_plan_scheme_base import CrashPlanSchemeBase
from scripts.cheat_sheet.base.cheat_base import CheatSheetBase
from scripts.executor.guest_side.deduce_mech import DeduceMech
from scripts.utils.exceptions import GuestExceptionForDebug
from scripts.utils.utils import alignToCeil, alignToFloor
from scripts.utils.const_var import CACHELINE_BYTES, ATOMIC_WRITE_BYTES
import scripts.vm_comm.memcached_wrapper as mc_wrapper
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.scheme_mechcomb.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class CrashPlanSchemeComb(CrashPlanSchemeBase):
    def __init__(self, op_entry : OpTraceEntry):
        # a list of generated crash plans
        self.cp_entry_list = []

        self.op_entry = op_entry

    @timeit
    def _gen_comb_at_fence(self, cache : WitcherCache):
        # respect to TSO
        all_seqs = []
        for cl in cache.cacheline_dict.values():
            for s in cl.stores_list:
                all_seqs.append(s.seq)

        if len(all_seqs) == 0:
            return

        num_stores_in_cache_lines = [len(cl.stores_list) for cl in cache.cacheline_dict.values()]

        num_combinations = 0
        for combination_length in range(0, len(num_stores_in_cache_lines) + 1):
            comb_list = list(itertools.combinations(num_stores_in_cache_lines, combination_length))
            for comb in comb_list:
                if len(comb) == 0:
                    num_combinations += 1
                else:
                    num_combinations += reduce(lambda x,y:x*y, comb)

        cp = CrashPlanEntry(CrashPlanType.Dummy, -1, -1, set(all_seqs), {-1}, 'Comb')
        cp.num_cp_entries = num_combinations
        self.cp_entry_list.append(cp)

        if log.debug:
            msg = f"number of comb cps: {num_combinations}, number of in-flight stores: {len(all_seqs)}"
            log.global_logger.debug(msg)

    @timeit
    def generate_crash_plans(self, ignore_nonatomic_write : bool,
                               nonatomic_as_one : bool,
                               sampling_nonatomic_write : bool):
        self.op_entry.convert_atomic_ops(ignore_nonatomic_write=ignore_nonatomic_write, nonatomic_as_one=nonatomic_as_one, sampling_nonatomic_write=sampling_nonatomic_write, force=False)

        cache = WitcherCache(EmptyBinaryFile())
        for op in self.op_entry.atomic_op_list:
            if isinstance(op, Store):
                cache.accept(op)
            elif isinstance(op, Flush):
                cache.accept(op)
            elif isinstance(op, Fence):
                self._gen_comb_at_fence(cache)
                cache.accept(op)
                cache.write_back_all_flushing_stores()
                cache.write_back_all_persisted_stores()
            else:
                assert False, "invalid op type, %s, %s" % (type(op), str(op))
