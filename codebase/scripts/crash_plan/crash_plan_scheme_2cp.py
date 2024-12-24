import os
import sys
import time
import random
import copy

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from scripts.cache_sim.witcher.cache.witcher_cache import WitcherCache
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr, OpTraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.instid_srcloc_reader.instid_src_loc_reader import InstIdSrcLocReader
from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason, MechPMStoreEntry
from scripts.crash_plan.crash_plan_entry import CrashPlanEntry
from scripts.crash_plan.crash_plan_type import CrashPlanType, CrashPlanSamplingType
from scripts.crash_plan.crash_plan_scheme_base import CrashPlanSchemeBase
from scripts.utils.exceptions import GuestExceptionForDebug
from scripts.executor.guest_side.deduce_mech import DeduceMech
from scripts.utils.utils import alignToCeil, alignToFloor
from scripts.utils.const_var import CACHELINE_BYTES, ATOMIC_WRITE_BYTES
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.scheme_2cp.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class CrashPlanScheme2CP(CrashPlanSchemeBase):
    def __init__(self, op_entry : OpTraceEntry, mech_deduce : DeduceMech):
        # a list of generated crash plans
        self.cp_entry_list = []

        self.op_entry = op_entry
        self.mech_deduce = mech_deduce

    @timeit
    def _gen_2cp_for_a_store(self, pmstore_entry : MechPMStoreEntry,
                             nonatomic_as_one : bool,
                             sampling_nonatomic_write : bool):
        seq = pmstore_entry.op.seq

        # 1. persist this store only among all in-flight stores

        # 1.1 find all stores that have been persisted before this store
        min_cluster_num = min(self.op_entry.in_flight_seq_cluster_map[seq])
        seq_set = set([seq])
        for cluster_num, seqs in self.op_entry.in_flight_cluster_flushing_map.items():
            if cluster_num < min_cluster_num:
                seq_set |= set(seqs)

        # 1.2 add dep stores, which must be persisted before this store
        if seq in self.op_entry.write_dep_seq_map:
            dbg_msg = "seq (%d)'s dep seqs (%s), (%s)" % \
                (seq, str(self.op_entry.write_dep_seq_map[seq]), seq_set | self.op_entry.write_dep_seq_map[seq])
            log.global_logger.debug(dbg_msg)
            seq_set |= self.op_entry.write_dep_seq_map[seq]

        # 1.3 considering TSO, the stores issued before this store and are in the same cacheline should be persisted before this store
        lower_addr = alignToFloor(pmstore_entry.op.addr, CACHELINE_BYTES)
        upper_addr = pmstore_entry.op.addr + pmstore_entry.op.size
        if upper_addr % CACHELINE_BYTES != 0:
            upper_addr = alignToCeil(upper_addr, CACHELINE_BYTES)
        same_cl_stores = self.op_entry.get_pm_ops_by_addr_range(lower_addr, upper_addr)
        for store in same_cl_stores:
            store : TraceEntry
            if store.type.isStoreSeries() and (min(seq_set) < store.seq < seq):
                seq_set.add(store.seq)

        # 1.4 create the cp entry
        dbg_msg = "persist itself: %d, and dep: %s, but no other seq." % (seq, str(seq_set))
        log.global_logger.debug(dbg_msg)
        cp = CrashPlanEntry(CrashPlanType.UnprotectedPersistSelf, pmstore_entry.op.instid, min(seq_set), seq_set, {seq}, pmstore_entry.op.to_result_str())

        # 1.5 sampling the this store
        start_addr = pmstore_entry.op.addr
        end_addr = start_addr + pmstore_entry.op.size
        if not nonatomic_as_one and (pmstore_entry.op.type.isMemset() or pmstore_entry.op.type.isMemTransStore()) and (start_addr//ATOMIC_WRITE_BYTES != end_addr//ATOMIC_WRITE_BYTES):

            if sampling_nonatomic_write:
                sample_addr = random.sample(range(start_addr, end_addr, ATOMIC_WRITE_BYTES), 1)[0]
                sample_addr = alignToFloor(sample_addr, ATOMIC_WRITE_BYTES)
                if sample_addr < start_addr:
                    sample_addr = start_addr
                cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                cp.sampling_seq = pmstore_entry.op.seq
                cp.sampling_addr = sample_addr
                self.cp_entry_list.append(cp)
            else:
                if start_addr % ATOMIC_WRITE_BYTES:
                    # handle the first not aligned bytes
                    tmp_cp = copy.copy(cp)
                    tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                    tmp_cp.sampling_seq = pmstore_entry.op.seq
                    tmp_cp.sampling_addr = start_addr
                    self.cp_entry_list.append(tmp_cp)
                    start_addr = alignToCeil(start_addr, ATOMIC_WRITE_BYTES)
                for addr in range(start_addr, end_addr):
                    tmp_cp = copy.copy(cp)
                    tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                    tmp_cp.sampling_seq = pmstore_entry.op.seq
                    tmp_cp.sampling_addr = addr
                    self.cp_entry_list.append(tmp_cp)
        else:
            self.cp_entry_list.append(cp)

        # 2. persist all other in-flight writes except this unprotected write

        # 2.1 find all other will-be-flushed stores
        max_cluster_num = max(self.op_entry.in_flight_seq_cluster_map[seq])
        dbg_msg = "cluster number for %d: %d" % (seq, max_cluster_num)
        log.global_logger.debug(dbg_msg)
        seq_set = set()
        for cluster_num, seqs in self.op_entry.in_flight_cluster_flushing_map.items():
            if cluster_num <= max_cluster_num:
                seq_set |= set(seqs)
                dbg_msg = "add other inflight stores for %d: %d, %s" % (cluster_num, seq, set(seqs))
                log.global_logger.debug(dbg_msg)

        # 2.2. remove itself
        if seq in seq_set:
            seq_set.remove(seq)

        # 2.3 remove stores that deps on this store
        for other_seq in seq_set.copy():
            if other_seq > seq and \
                    other_seq in self.op_entry.write_dep_seq_map and \
                    seq in self.op_entry.write_dep_seq_map[other_seq]:
                seq_set.remove(other_seq)
                dbg_msg = "not persist itself remove dep seq: %d" % (other_seq)
                log.global_logger.debug(dbg_msg)

        # 2.3 considering TSO, the stores issued after this store and are in the same cacheline should be persisted after this store
        lower_addr = alignToFloor(pmstore_entry.op.addr, CACHELINE_BYTES)
        upper_addr = pmstore_entry.op.addr + pmstore_entry.op.size
        if upper_addr % CACHELINE_BYTES != 0:
            upper_addr = alignToCeil(upper_addr, CACHELINE_BYTES)
        same_cl_stores = self.op_entry.get_pm_ops_by_addr_range(lower_addr, upper_addr)
        for store in same_cl_stores:
            store : TraceEntry
            if store.type.isStoreSeries() and (store.seq > seq):
                if store.seq in seq_set:
                    seq_set.remove(store.seq)

        # 2.4 create the cp entry
        dbg_msg = "persist all other seq: %s but not itself: %d" % (str(seq_set), seq)
        log.global_logger.debug(dbg_msg)
        min_seq = seq if len(seq_set) == 0 else min(seq, min(seq_set))
        cp = CrashPlanEntry(CrashPlanType.UnprotectedPersistOther, pmstore_entry.op.instid, min_seq, seq_set, {seq}, pmstore_entry.op.to_result_str())

        # 2.5 sampling the this store
        start_addr = pmstore_entry.op.addr
        end_addr = start_addr + pmstore_entry.op.size
        if not nonatomic_as_one and (pmstore_entry.op.type.isMemset() or pmstore_entry.op.type.isMemTransStore()) and (start_addr//ATOMIC_WRITE_BYTES != end_addr//ATOMIC_WRITE_BYTES):

            if sampling_nonatomic_write:
                sample_addr = random.sample(range(start_addr, end_addr, ATOMIC_WRITE_BYTES), 1)[0]
                sample_addr = alignToFloor(sample_addr, ATOMIC_WRITE_BYTES)
                if sample_addr < start_addr:
                    sample_addr = start_addr
                cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                cp.sampling_seq = pmstore_entry.op.seq
                cp.sampling_addr = sample_addr
                self.cp_entry_list.append(cp)
            else:
                if start_addr % ATOMIC_WRITE_BYTES:
                    # handle the first not aligned bytes
                    tmp_cp = copy.copy(cp)
                    tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                    tmp_cp.sampling_seq = pmstore_entry.op.seq
                    tmp_cp.sampling_addr = start_addr
                    self.cp_entry_list.append(tmp_cp)
                    start_addr = alignToCeil(start_addr, ATOMIC_WRITE_BYTES)
                for addr in range(start_addr, end_addr):
                    tmp_cp = copy.copy(cp)
                    tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                    tmp_cp.sampling_seq = pmstore_entry.op.seq
                    tmp_cp.sampling_addr = addr
                    self.cp_entry_list.append(tmp_cp)
        else:
            self.cp_entry_list.append(cp)

    @timeit
    def generate_crash_plans(self, ignore_nonatomic_write : bool,
                               nonatomic_as_one : bool,
                               sampling_nonatomic_write : bool):
        self.mech_deduce.deduce_pmstore(self.op_entry)

        for pmstore_entry in self.mech_deduce.pmstore_reason.entry_list:
            pmstore_entry : MechPMStoreEntry

            if ignore_nonatomic_write and (pmstore_entry.op.type.isMemset() or pmstore_entry.op.type.isMemTransStore()):
                dbg_msg = "entry %d, %s, %d is memory copy or set, ignore it." % (pmstore_entry.op.seq, hex(pmstore_entry.op.addr), pmstore_entry.op.size)
                log.global_logger.debug(dbg_msg)
                continue

            # check if the in-flight cluster contains this pm store
            if pmstore_entry.op.seq not in self.op_entry.in_flight_seq_cluster_map:
                # no such record!
                err_msg = "seq not in in-flight cluster map: %s, %s" % (str(pmstore_entry), str(self.op_entry.in_flight_seq_cluster_map))
                log.global_logger.error(err_msg)
                raise GuestExceptionForDebug(err_msg)

            self._gen_2cp_for_a_store(pmstore_entry, nonatomic_as_one, sampling_nonatomic_write)
