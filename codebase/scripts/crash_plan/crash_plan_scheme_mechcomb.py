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
from scripts.cache_sim.witcher.cache.atomic_op import Fence, Store
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
from scripts.utils.utils import alignToCeil, alignToFloor, getTimestamp
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

class CrashPlanSchemeMechComb(CrashPlanSchemeBase):
    def __init__(self, trace_reader : TraceReader, stinfo_index : StInfoIndex, op_entry : OpTraceEntry, mech_deduce : DeduceMech):
        # a list of generated crash plans
        self.cp_entry_list = []

        self.trace_reader = trace_reader
        self.stinfo_index = stinfo_index
        self.op_entry = op_entry

        self.mech_deduce = mech_deduce

    @timeit
    def deduce_mech(self):
        self.mech_deduce.deduce_pmstore(self.op_entry)
        self.mech_deduce.deduce_memset(self.op_entry)
        self.mech_deduce.deduce_memcpy(self.op_entry)
        self.mech_deduce.deduce_link(self.op_entry, self.stinfo_index)
        self.mech_deduce.deduce_undojnl(self.op_entry)
        self.mech_deduce.deduce_replication(self.op_entry)
        self.mech_deduce.deduce_lsw(self.op_entry, self.stinfo_index)

    @timeit
    def _gen_2cp_for_a_store(self, pmstore_entry : MechPMStoreEntry,
                             nonatomic_as_one : bool,
                             sampling_nonatomic_write : bool,
                             persist_self,
                             persist_other,
                             cp_type : CrashPlanType = None):
        seq = pmstore_entry.op.seq

        if persist_self:
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
                    if cp_type:
                        cp.type = cp_type
                    self.cp_entry_list.append(cp)
                else:
                    if start_addr % ATOMIC_WRITE_BYTES:
                        # handle the first not aligned bytes
                        tmp_cp = copy.copy(cp)
                        tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                        tmp_cp.sampling_seq = pmstore_entry.op.seq
                        tmp_cp.sampling_addr = start_addr
                        if cp_type:
                            tmp_cp.type = cp_type
                        self.cp_entry_list.append(tmp_cp)
                        start_addr = alignToCeil(start_addr, ATOMIC_WRITE_BYTES)
                    for addr in range(start_addr, end_addr):
                        tmp_cp = copy.copy(cp)
                        tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                        tmp_cp.sampling_seq = pmstore_entry.op.seq
                        tmp_cp.sampling_addr = addr
                        if cp_type:
                            tmp_cp.type = cp_type
                        self.cp_entry_list.append(tmp_cp)
            else:
                if cp_type:
                    cp.type = cp_type
                self.cp_entry_list.append(cp)

        if persist_other:
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
                    if cp_type:
                        cp.type = cp_type
                    self.cp_entry_list.append(cp)
                else:
                    if start_addr % ATOMIC_WRITE_BYTES:
                        # handle the first not aligned bytes
                        tmp_cp = copy.copy(cp)
                        tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                        tmp_cp.sampling_seq = pmstore_entry.op.seq
                        tmp_cp.sampling_addr = start_addr
                        if cp_type:
                            tmp_cp.type = cp_type
                        self.cp_entry_list.append(tmp_cp)
                        start_addr = alignToCeil(start_addr, ATOMIC_WRITE_BYTES)
                    for addr in range(start_addr, end_addr):
                        tmp_cp = copy.copy(cp)
                        tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                        tmp_cp.sampling_seq = pmstore_entry.op.seq
                        tmp_cp.sampling_addr = addr
                        if cp_type:
                            tmp_cp.type = cp_type
                        self.cp_entry_list.append(tmp_cp)
            else:
                if cp_type:
                    cp.type = cp_type
                self.cp_entry_list.append(cp)

    @timeit
    def _gen_comb_for_stores(self,
                             cluster_number : int,
                             tobe_comb_seq_set : set,
                             nonatomic_as_one : bool,
                             sampling_nonatomic_write : bool,
                             cp_type : CrashPlanType = None):
        all_persisted_seq_set : set = set()
        for i in range(cluster_number):
            if i in self.op_entry.in_flight_cluster_seq_map:
                all_persisted_seq_set |= set(self.op_entry.in_flight_cluster_seq_map[i])

        all_inflight_seq_set : set = set()
        other_inflight_seq_set : set = set()
        if cluster_number not in self.op_entry.in_flight_cluster_seq_map:
            return
        all_inflight_seq_set = set(self.op_entry.in_flight_cluster_seq_map[cluster_number])

        all_persisted_seq_set -= all_inflight_seq_set
        other_inflight_seq_set = all_inflight_seq_set - tobe_comb_seq_set

        entry_list = []
        for seq in tobe_comb_seq_set:
            pmstore_entry : MechPMStoreEntry = self.mech_deduce.pmstore_reason.get_entry_by_seq(seq)
            pmstore_entry = pmstore_entry[0]
            entry_list.append(pmstore_entry.op)

        atomic_ops = convert_entry_list(entry_list, ignore_nonatomic_write=False, nonatomic_as_one=nonatomic_as_one, sampling_nonatomic_write=sampling_nonatomic_write)
        atomic_ops.sort(key=lambda x:x.seq)
        if len(atomic_ops) == 0:
            return

        # mech filter out lots of stores, we can handle the combination
        visited : set = set()
        for combination_length in range(0, len(atomic_ops) + 1):
            comb_list = list(itertools.combinations(atomic_ops, combination_length))

            for comb in comb_list:
                # persisting this com but not other in-flight stores
                comb = list(comb)
                comb.sort(key=lambda x:x.seq)
                tobe_persist_seq_set = set([x.seq for x in comb])

                # adding must happend before writes (e.g., TSO)
                dep_seq_set :set = set()
                for seq in tobe_persist_seq_set:
                    if seq in self.op_entry.write_dep_seq_map:
                        dep_seq_set |= self.op_entry.write_dep_seq_map[seq]
                tobe_persist_seq_set |= dep_seq_set

                # adding other seqs that are not in-flight
                tobe_persist_seq_set |= all_persisted_seq_set

                # check if visited
                # sampled ops could have the same seq, thus, adding addr as a part of the key
                visited_key : tuple = ((tuple(tobe_persist_seq_set), tuple([x.addr for x in comb])))
                if visited_key in visited:
                    continue
                else:
                    visited.add(visited_key)

                cp = CrashPlanEntry(CrashPlanType.CombPersistSelf, -1, self.op_entry.min_seq, tobe_persist_seq_set, {}, str(sorted(list(tobe_persist_seq_set))))
                self.cp_entry_list.append(cp)

                if len(other_inflight_seq_set) == 0:
                    self.cp_entry_list[-1].type = CrashPlanType.CombPersist

                else:
                    # persisting protected stores but not this comb
                    tobe_persist_seq_set = all_inflight_seq_set - set([x.seq for x in comb])

                    # adding must happend before writes (e.g., TSO)
                    dep_seq_set :set = set()
                    for seq in tobe_persist_seq_set:
                        if seq in self.op_entry.write_dep_seq_map:
                            dep_seq_set |= self.op_entry.write_dep_seq_map[seq]
                    tobe_persist_seq_set |= dep_seq_set

                    # adding other seqs that are not in-flight
                    tobe_persist_seq_set |= all_persisted_seq_set

                    cp = CrashPlanEntry(CrashPlanType.CombPersistOther, -1, self.op_entry.min_seq, tobe_persist_seq_set, {}, str(sorted(list(tobe_persist_seq_set))))
                    self.cp_entry_list.append(cp)

        return

        if len(tobe_comb_seq_set) > 0:
            # No real crash plans will be generated due to the large number
            cache = WitcherCache(EmptyBinaryFile())
            for op in atomic_ops:
                cache.accept(op)

            # respect to TSO
            num_stores_in_cache_lines = [len(cl.stores_list) for cl in cache.cacheline_dict.values()]

            num_combinations = 0
            for combination_length in range(0, len(num_stores_in_cache_lines) + 1):
                comb_list = list(itertools.combinations(num_stores_in_cache_lines, combination_length))
                for comb in comb_list:
                    if len(comb) == 0:
                        num_combinations += 1
                    else:
                        num_combinations += reduce(lambda x,y:x*y, comb)

            if len(other_inflight_seq_set) > 0:
                # for each combination, persisting or not persisting other in-flight stores
                num_combinations *= 2

            cp = CrashPlanEntry(CrashPlanType.Dummy, -1, -1, tobe_comb_seq_set, {-1}, 'Comb')
            cp.num_cp_entries = num_combinations
            self.cp_entry_list.append(cp)

            if log.debug:
                msg = f"number of comb cps: {num_combinations}, {len(tobe_comb_seq_set), {len(other_inflight_seq_set)}}"
                log.global_logger.debug(msg)

        else:
            # generate real crash plans
            # cache = WitcherCache(EmptyBinaryFile())
            # for op in atomic_ops:
            #     cache.accept(op)

            # # respect to TSO
            # stores_in_cache_lines = [[s.seq for s in cl.stores_list] for cl in cache.cacheline_dict.values()]

            # for combination_length in range(0, len(stores_in_cache_lines) + 1):
            #     comb_list = list(itertools.combinations(stores_in_cache_lines, combination_length))
            #     for comb in comb_list:
            #         # comb: [[seq1, seq3], [seq2, seq4]]

            #         if len(comb) == 0:
            #             num_combinations += 1
            #         else:
            #             num_combinations += reduce(lambda x,y:x*y, comb)

            for combination_length in range(0, len(atomic_ops) + 1):
                comb_list = list(itertools.combinations(atomic_ops, combination_length))

                for comb in comb_list:
                    # persisting this com but not other in-flight stores
                    tobe_persist_seq_set = set([x.seq for x in comb])

                    # adding must happend before writes (e.g., TSO)
                    dep_seq_set :set = set()
                    for seq in tobe_persist_seq_set:
                        if seq in self.op_entry.write_dep_seq_map:
                            dep_seq_set |= self.op_entry.write_dep_seq_map[seq]
                    tobe_persist_seq_set |= dep_seq_set

                    # adding other seqs that are not in-flight
                    tobe_persist_seq_set |= all_persisted_seq_set

                    cp = CrashPlanEntry(CrashPlanType.CombPersistSelf, -1, self.op_entry.min_seq, tobe_persist_seq_set, {}, str(sorted(list(tobe_persist_seq_set))))
                    self.cp_entry_list.append(cp)

                    if len(other_inflight_seq_set) == 0:
                        self.cp_entry_list[-1].type = CrashPlanType.CombPersist

                    else:
                        # persisting protected stores but not this comb
                        tobe_persist_seq_set = all_inflight_seq_set - set([x.seq for x in comb])

                        # adding must happend before writes (e.g., TSO)
                        dep_seq_set :set = set()
                        for seq in tobe_persist_seq_set:
                            if seq in self.op_entry.write_dep_seq_map:
                                dep_seq_set |= self.op_entry.write_dep_seq_map[seq]
                        tobe_persist_seq_set |= dep_seq_set

                        # adding other seqs that are not in-flight
                        tobe_persist_seq_set |= all_persisted_seq_set

                        cp = CrashPlanEntry(CrashPlanType.CombPersistOther, -1, self.op_entry.min_seq, tobe_persist_seq_set, {}, str(sorted(list(tobe_persist_seq_set))))
                        self.cp_entry_list.append(cp)

    @timeit
    def generate_crash_plans(self, ignore_nonatomic_write : bool,
                               nonatomic_as_one : bool,
                               sampling_nonatomic_write : bool):
        self.deduce_mech()

        cluster_number_to_unprotected_seqs : dict = dict()
        # the seq set for mechanisms. Only persist itself, and only persist others.
        persist_self_seq_set, persist_other_seq_set, mech_seq_set = self.mech_deduce.get_persist_seq(check_unsafe=False, check_recovery=True)

        for pmstore_entry in self.mech_deduce.pmstore_reason.entry_list:
            pmstore_entry : MechPMStoreEntry
            seq = pmstore_entry.op.seq

            if seq in persist_self_seq_set:
                self._gen_2cp_for_a_store(pmstore_entry, nonatomic_as_one, sampling_nonatomic_write, persist_self=True, persist_other=False,  cp_type=CrashPlanType.MechPersistSelf)
            if seq in persist_other_seq_set:
                self._gen_2cp_for_a_store(pmstore_entry, nonatomic_as_one, sampling_nonatomic_write, persist_self=False, persist_other=True,  cp_type=CrashPlanType.MechPersistOther)
            if seq in mech_seq_set:
                # skip this seq, mech-protected stores
                # this is the superset of persist_self_seq_set and persist_other_seq_set
                continue
            else:
                # after checking the seqs in mech, go to the regular 2cp generation scheme
                if ignore_nonatomic_write and (pmstore_entry.op.type.isMemset() or pmstore_entry.op.type.isMemTransStore()):
                    if log.debug:
                        dbg_msg = "entry %d, %s, %d is memory copy or set, ignore it." % (seq, hex(pmstore_entry.op.addr), pmstore_entry.op.size)
                        log.global_logger.debug(dbg_msg)
                    continue

                # check if the in-flight cluster contains this pm store
                if seq not in self.op_entry.in_flight_seq_cluster_map:
                    # no such record!
                    err_msg = "seq not in in-flight cluster map: %s, %s" % (str(pmstore_entry), str(self.op_entry.in_flight_seq_cluster_map))
                    log.global_logger.error(err_msg)
                    raise GuestExceptionForDebug(err_msg)
                else:
                    for cluster_number in self.op_entry.in_flight_seq_cluster_map[seq]:
                        if cluster_number not in cluster_number_to_unprotected_seqs:
                            cluster_number_to_unprotected_seqs[cluster_number] = set()
                        cluster_number_to_unprotected_seqs[cluster_number].add(seq)

        # generate crash plans based by combining stores
        for cluster_number, tobe_comb_seq_set in cluster_number_to_unprotected_seqs.items():
            self._gen_comb_for_stores(cluster_number, tobe_comb_seq_set, nonatomic_as_one, sampling_nonatomic_write)

    @timeit
    def sending_details_to_mc(self, trace_reader : TraceReader, op_entry):
        '''
        Sending some detailed information to Memcached for debugging.
        A lots of object accesses here, may need to update when some class changes.
        '''
        jnl_seqs : set = set()
        if self.mech_deduce.undojnl_reason:
            for jnl_entry in self.mech_deduce.undojnl_reason.entry_list:
                jnl_seqs |= jnl_entry.get_all_seq()

        rep_seqs : set = set()
        if self.mech_deduce.rep_reason:
            for rep_entry in self.mech_deduce.rep_reason.entry_list:
                rep_seqs |= rep_entry.get_all_seq()

        lsw_seqs : set = set()
        if self.mech_deduce.lsw_reason_list:
            for lsw_reason in self.mech_deduce.lsw_reason_list:
                for lsw_entry in lsw_reason.entry_list:
                    lsw_seqs |= lsw_entry.get_all_seq()

        flush_seqs : list = list()
        fence_seqs : list = list()
        for seq, entry_list in trace_reader.seq_entry_map.items():
            if entry_list[0].type.isFlushTy():
                flush_seqs.append(seq)
            if entry_list[0].type.isFenceTy():
                fence_seqs.append(seq)
        flush_seqs = list(set(flush_seqs))
        fence_seqs = list(set(fence_seqs))
        flush_seqs = [x for x in flush_seqs if op_entry.min_seq <= x <= op_entry.max_seq]
        fence_seqs = [x for x in fence_seqs if op_entry.min_seq <= x <= op_entry.max_seq]
        flush_seqs.sort(reverse=True)
        fence_seqs.sort(reverse=True)

        msg = 'seq,fence_seq,addr,size,struct,var,src'

        if not self.mech_deduce.pmstore_reason:
            msg = 'No PMStore Reason!'
        else:
            for entry in self.mech_deduce.pmstore_reason.entry_list:
                entry : MechPMStoreEntry

                while len(flush_seqs) > 0 and entry.op.seq > flush_seqs[-1]:
                    msg += f'flush:{flush_seqs.pop()}\n'
                while len(fence_seqs) > 0 and entry.op.seq > fence_seqs[-1]:
                    msg += f'fence:{fence_seqs.pop()}\n'
                msg += f'{entry.op.seq},{entry.fence_op.seq if entry.fence_op else 0},0x{entry.addr:x},{entry.size},{entry.op.stinfo_match.stinfo.struct_name if entry.op.stinfo_match else "na"},{[x.var_name for x in entry.op.var_list] if entry.op.var_list else []},{entry.op.src_entry}'
                if entry.op.seq in jnl_seqs:
                    msg += ',jnl'
                if entry.op.seq in rep_seqs:
                    msg += ',rep'
                if entry.op.seq in lsw_seqs:
                    msg += ',lsw'
                msg += '\n'

            while len(flush_seqs) > 0:
                msg += f'flush:{flush_seqs.pop()}\n'
            while len(fence_seqs) > 0:
                msg += f'flush:{fence_seqs.pop()}\n'

        cp_count_map = dict()
        cp_msg = ''
        for cp in self.cp_entry_list:
            cp : CrashPlanEntry
            if cp.type not in cp_count_map:
                cp_count_map[cp.type] = 0
            cp_count_map[cp.type] += 1
        for tp, count in cp_count_map.items():
            cp_msg += f'{tp}: {count}\n'
        for cp in self.cp_entry_list:
            cp_msg += f'{cp.type.value},{cp.start_seq},{cp.exp_data_seqs},{cp.sampling_type.value},{cp.persist_seqs}\n'

        msg = msg + '\n\n' + cp_msg

        key = 'detailed_info_count'
        if mc_wrapper.mc_add_wrapper(mc_wrapper.glo_mc_pool_client, key, 0):
            pass

        num = mc_wrapper.mc_incr_wrapper(mc_wrapper.glo_mc_pool_client, key, 1)
        if num == None:
            return

        if log.debug:
            log.global_logger.debug(msg)

        report_time = getTimestamp()
        key = f'detailed_info.{num}'
        value = [report_time, msg]
        if self.mech_deduce.basename:
            value.append(self.mech_deduce.basename)
        if self.mech_deduce.op_name_list:
            value.append(len(self.mech_deduce.op_name_list))
            value.append(self.mech_deduce.op_name_list)

        mc_wrapper.mc_set_wrapper(mc_wrapper.glo_mc_pool_client, key, value)
