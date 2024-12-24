import os
import sys
import logging
import glob
import datetime
import copy
from itertools import combinations

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.tools_proc.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.tools_proc.annot_reader.annot_reader import AnnotReader
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex, StructInfo, AddrToStInfoEntry, StructMemberVar
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr
from scripts.witcher.cache.entry_op_conv import convert_seq_entrylist_dict, convert_entry_list_with_sampling_option
from scripts.witcher.binary_file.binary_file import EmptyBinaryFile
from scripts.witcher.cache.atomic_op import Store, Flush, Fence
from scripts.witcher.cache.witcher_cache import WitcherCache
from scripts.witcher.cache.reorder_simulator import ReorderSimulator, CacheLineReorderSimulator
from logic_reason.mech.mech_undojnl.mech_undojnl_reason import MechUndoJnlEntry, MechUndoJnlReason
from logic_reason.mech.mech_store.mech_pmstore_reason import MechPMStoreReason, MechPMStoreEntry
from logic_reason.mech.mech_store.mech_cirtical_pmstore_reason import MechCirticalPMStoreReason
from logic_reason.mech.mech_link.mech_link_reason import MechLinkEntry, MechLinkReason
from logic_reason.mech.mech_lsw.mech_lsw_reason import MechLSWEntry, MechLSWReason
from logic_reason.mech.mech_memcpy.mech_memcpy_reason import MechMemcpyEntry, MechMemcpyReason
from logic_reason.mech.mech_replication.mech_repl_reason import MechReplEntry, MechReplReason
from logic_reason.crash_plan.crash_plan_entry import CrashPlanEntry, CrashPlanType, CrashPlanSamplingType
from scripts.utils.utils import alignToFloor, alignToCeil, isOverlapping
from scripts.utils.logger import global_logger
from scripts.utils.const_var import ATOMIC_WRITE_BYTES, CACHELINE_BYTES

glo_use_mech_2cp_with_sampling        = False
glo_use_mech_2cp_without_sampling     = False
glo_use_mech_2cp_nonatomic_as_single  = True
glo_use_2cp_with_sampling             = False
glo_use_2cp_without_sampling          = False
glo_use_2cp_nonatomic_as_single       = False
glo_use_mech_comb_with_sampling       = False
glo_use_mech_comb_without_sampling    = False
glo_use_mech_comb_nonatomic_as_single = False

glo_consider_cl_prefix_in_2cp         = False

glo_use_cachelinereordering_scheme    = False
glo_cachelinereordering_no_cp_pickle  = True

glo_use_chipmunk_scheme               = False
glo_use_chipmunk_no_cp_pickle         = True

glo_use_vinter_scheme                 = False
glo_use_vinter_no_cp_pickle           = True
glo_use_vinter_overlap_cacheline      = False

glo_dump_cp_result_fname = "summary.gen_cp.txt"

class CrashPlanGenerator:
    def __init__(self,
                 split_entry : OpTraceEntry,
                 pmstore_reason : MechPMStoreReason,
                 lsw_reason : MechLSWReason,
                 rep_reason : MechReplReason,
                 undojnl_reason : MechUndoJnlReason) -> None:
        global glo_not_need_cp_pickle, glo_comb_crash_plans

        self.entry_list = []
        self.pre_oracle_cp = None
        self.post_oracle_cp = None

        self.dump_data = ""

        # no pm stores
        if len(pmstore_reason.entry_list) == 0:
            return

        # if glo_comb_crash_plans and not glo_not_need_cp_pickle:
        #     assert False, "please make sure you want to use the combinatorial approach!!"

        self.gen_cp_schemes(split_entry, pmstore_reason, lsw_reason, rep_reason, undojnl_reason)

    #     self.__init(split_entry, pmstore_reason, lsw_reason, rep_reason, undojnl_reason)


    # def __init(self,
    #            split_entry : OpTraceEntry,
    #            pmstore_reason : MechPMStoreReason,
    #            lsw_reason : MechLSWReason,
    #            rep_reason : MechReplReason,
    #            undojnl_reason : MechUndoJnlReason) -> None:
    #     global glo_disable_mech

    #     if not glo_disable_mech:
    #         # 1. crash plan for each lsw reason entry
    #         if lsw_reason:
    #             self.__init_lsw(lsw_reason, pmstore_reason)

    #         # 2. crash plan for each rep reason entry
    #         if rep_reason:
    #             self.__init_rep(rep_reason, pmstore_reason)

    #         # 3. crash plan for each undo journal entry
    #         if undojnl_reason:
    #             self.__init_undojnl(undojnl_reason, pmstore_reason)

    #     # 4. crash plan to unprotected entries
    #     self.__init_unguarded_stores(split_entry, pmstore_reason, lsw_reason,
    #                                    rep_reason, undojnl_reason)

    #     # 5. oracle crash plans
    #     self.__init_oracles(pmstore_reason)

    # def __init_lsw(self, lsw_reason : MechLSWReason, pmstore_reason : MechPMStoreReason):
    #     for entry in lsw_reason.entry_list:
    #         entry : MechLSWEntry
    #         min_seq = entry.tail_store.op.seq
    #         safe_stores = entry.get_safe_data_seq_list()
    #         unsafe_stores = entry.get_unsafe_data_seq_list()
    #         if safe_stores or unsafe_stores:
    #             min_seq = min(safe_stores + unsafe_stores)

    #         # 1. crash plan for this mech
    #         # no crash plan for lsw
    #         # cp = CrashPlanEntry(CrashPlanType.LSWSafe, entry.tail_store.op.seq,
    #         #                     {}, {}, entry.tail_store.op.to_result_str())
    #         # self.entry_list.append(cp)

    #         # 2. crash plan for unprotected stores
    #         persist_seqs = [entry.tail_store.op.seq]
    #         if safe_stores:
    #             persist_seqs += safe_stores
    #         for store_seq in unsafe_stores:
    #             # does not persist unsafe store.
    #             pmstore_entry : MechPMStoreEntry = pmstore_reason.get_entry_by_seq(store_seq)
    #             cp = CrashPlanEntry(CrashPlanType.LSWUnsafe, min_seq,
    #                                 set(persist_seqs), {store_seq},
    #                                 pmstore_entry.op.to_result_str())
    #             self.entry_list.append(cp)
    #             persist_seqs.append(store_seq)

    # def __init_rep(self, rep_reason : MechReplReason, pmstore_reason : MechPMStoreReason):
    #     for entry in rep_reason.entry_list:
    #         entry : MechReplEntry
    #         min_seq = entry.store.op_st.seq
    #         safe_stores = entry.get_safe_data_seq_list()
    #         unsafe_stores = entry.get_unsafe_data_seq_list()
    #         if safe_stores or unsafe_stores:
    #             min_seq = min(safe_stores + unsafe_stores)

    #         # 1. crash plan for this mech
    #         # 1.1 crash at writing the primary
    #         if len(entry.src_update_stores) > 0:
    #             op = entry.src_update_stores[-1].op
    #             cp = CrashPlanEntry(CrashPlanType.RepSafe, op.seq,
    #                                 {}, {}, op.to_result_str())
    #             self.entry_list.append(cp)
    #         # 1.2 crash at copying to the replica
    #         cp = CrashPlanEntry(CrashPlanType.RepSafe, entry.store.op_st.seq,
    #                             {}, {}, entry.store.op_st.to_result_str())
    #         self.entry_list.append(cp)

    #         # 2. crash plan for unprotected stores
    #         persist_seqs = [entry.store.op_st.seq]
    #         if safe_stores:
    #             persist_seqs += safe_stores
    #         for store_seq in unsafe_stores:
    #             # does not persist unsafe store.
    #             pmstore_entry : MechPMStoreEntry = pmstore_reason.get_entry_by_seq(store_seq)
    #             cp = CrashPlanEntry(CrashPlanType.RepUnsafe, min_seq,
    #                                 set(persist_seqs), {store_seq},
    #                                 pmstore_entry.op.to_result_str())
    #             self.entry_list.append(cp)
    #             persist_seqs.append(store_seq)

    # def __init_undojnl(self, undojnl_reason : MechUndoJnlReason, pmstore_reason : MechPMStoreReason):
    #     for entry in undojnl_reason.entry_list:
    #         entry : MechUndoJnlEntry
    #         min_seq = entry.tail_store.op.seq
    #         safe_stores = entry.get_safe_entry_store_seq_list()
    #         unsafe_stores = entry.get_unsafe_entry_store_seq_list()
    #         if safe_stores or unsafe_stores:
    #             min_seq = min(safe_stores + unsafe_stores)

    #         # 1. crash plan for this mech
    #         if entry.head_store:
    #             cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, entry.head_store.op.seq,
    #                                 {}, {}, entry.tail_store.op.to_result_str())
    #             self.entry_list.append(cp)
    #         elif len(entry.jnl_inplace_stores) > 0:
    #             op = entry.jnl_inplace_stores[-1].op
    #             cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, op.seq + 1,
    #                                 {}, {}, op.to_result_str())
    #             self.entry_list.append(cp)
    #         elif entry.cheat_sheet and not entry.cheat_sheet.is_pre_allocation:
    #             cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, entry.tail_store.op.seq + 1,
    #                                 {}, {}, entry.tail_store.op.to_result_str())
    #             self.entry_list.append(cp)
    #         elif entry.cheat_sheet and entry.cheat_sheet.is_pre_allocation:
    #             op = entry.jnl_safe_stores[-1].op
    #             cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, op.seq + 1,
    #                                 {}, {}, op.to_result_str())
    #             self.entry_list.append(cp)
    #         else:
    #             cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, entry.tail_store.op.seq + 1,
    #                                 {}, {}, entry.tail_store.op.to_result_str())
    #             self.entry_list.append(cp)

    #         # 2. crash plan for unprotected entry stores
    #         persist_seqs = [entry.tail_store.op.seq]
    #         if safe_stores:
    #             persist_seqs += safe_stores
    #         for store_seq in unsafe_stores:
    #             # does not persist unsafe store.
    #             pmstore_entry : MechPMStoreEntry = pmstore_reason.get_entry_by_seq(store_seq)
    #             cp = CrashPlanEntry(CrashPlanType.UndojnlUnsafe, min_seq,
    #                                 set(persist_seqs), {store_seq},
    #                                 pmstore_entry.op.to_result_str())
    #             self.entry_list.append(cp)
    #             persist_seqs.append(store_seq)

    #         # 3. crash plan for unsafe destination in-place stores
    #         tail_seq = entry.tail_store.op.seq
    #         for store in entry.jnl_unsafe_inplace_stores:
    #             if store.op.seq < tail_seq:
    #                 # update before the tail update
    #                 # persist this store.
    #                 cp = CrashPlanEntry(CrashPlanType.UndojnlUnsafeInplace, store.op.seq,
    #                                 {store.op.seq}, {store.op.seq},
    #                                 store.op.to_result_str())
    #                 self.entry_list.append(cp)
    #             else:
    #                 # update after the head update or after the trace
    #                 # persist this store.
    #                 cp = CrashPlanEntry(CrashPlanType.UndojnlUnsafeInplace, store.op.seq,
    #                                 {store.op.seq}, {store.op.seq},
    #                                 store.op.to_result_str())
    #                 self.entry_list.append(cp)

    # def __init_unguarded_stores(self,
    #                             split_entry : OpTraceEntry,
    #                             pmstore_reason : MechPMStoreReason,
    #                             lsw_reason : MechLSWReason,
    #                             rep_reason : MechReplReason,
    #                             undojnl_reason : MechUndoJnlReason) -> None:
    #     global glo_disable_mech, glo_not_need_cp_pickle, glo_comb_crash_plans

    #     guarded_seqs = []
    #     if not glo_disable_mech:
    #         if lsw_reason:
    #             for entry in lsw_reason.entry_list:
    #                 guarded_seqs += entry.get_opid_seq_list()
    #                 guarded_seqs += entry.get_safe_data_seq_list()
    #                 guarded_seqs += entry.get_unsafe_data_seq_list()
    #         if rep_reason:
    #             for entry in rep_reason.entry_list:
    #                 guarded_seqs += entry.get_opid_seq_list()
    #                 guarded_seqs += entry.get_safe_data_seq_list()
    #                 guarded_seqs += entry.get_unsafe_data_seq_list()
    #         if undojnl_reason:
    #             for entry in undojnl_reason.entry_list:
    #                 guarded_seqs += entry.get_opid_seq_list()
    #                 guarded_seqs += entry.get_safe_data_seq_list()
    #                 guarded_seqs += entry.get_unsafe_data_seq_list()

    #     guarded_seqs = set(guarded_seqs)
    #     unguarded_seqs = set([x.op.seq for x in pmstore_reason.entry_list])
    #     unguarded_seqs = list(unguarded_seqs - guarded_seqs)
    #     unguarded_seqs.sort()

    #     if glo_not_need_cp_pickle:
    #         cp = CrashPlanEntry(CrashPlanType.Unguarded, 0, {}, {}, 'no_pickle')
    #         if glo_comb_crash_plans:
    #             num_combinations = 0
    #             unguarded_seqs = set(unguarded_seqs)

    #             for _, in_flight_seq_list in split_entry.in_flight_cluster_seq_map.items():
    #                 in_flight_seqs = set(in_flight_seq_list)
    #                 if len(in_flight_seqs) > 0 and (unguarded_seqs & in_flight_seqs):
    #                     num_combinations += 2**len(in_flight_seqs)

    #             cp.num_cp_entries = num_combinations
    #         else:
    #             cp.num_cp_entries = len(unguarded_seqs) * 2

    #         self.entry_list.append(cp)
    #         return

    #     for seq in unguarded_seqs:
    #         pmstore_entry : MechPMStoreEntry = pmstore_reason.get_entry_by_seq(seq)

    #         if seq not in split_entry.in_flight_seq_cluster_map:
    #             err_msg = "seq not in in-flight cluster map: %s, %s" % (str(pmstore_entry), str(split_entry.in_flight_seq_cluster_map))
    #             global_logger.error(err_msg)
    #             assert False, err_msg

    #         # two crash plans for unguarded write
    #         # 1. persist unguarded write only among all in-flight writes
    #         min_cluster_num = min(split_entry.in_flight_seq_cluster_map[seq])
    #         seq_list = [seq]
    #         for cluster_num, seqs in split_entry.in_flight_cluster_flushing_map.items():
    #             if cluster_num < min_cluster_num:
    #                 seq_list += seqs
    #         cp = CrashPlanEntry(CrashPlanType.Unguarded, min(seq_list), set(seq_list), {seq},
    #                             pmstore_entry[0].op.to_result_str())
    #         self.entry_list.append(cp)

    #         # 2. persist all other in-flight writes except this unguarded write
    #         max_cluster_num = max(split_entry.in_flight_seq_cluster_map[seq])
    #         seq_list = []
    #         for cluster_num, seqs in split_entry.in_flight_cluster_flushing_map.items():
    #             if cluster_num <= max_cluster_num:
    #                 seq_list += seqs
    #         seq_set = set(seq_list)
    #         if seq in seq_set:
    #             seq_set.remove(seq)
    #         cp = CrashPlanEntry(CrashPlanType.Unguarded, min(seq, min(seq_list)), seq_set, {seq},
    #                             pmstore_entry[0].op.to_result_str())
    #         self.entry_list.append(cp)

    # def __init_oracles(self, pmstore_reason : MechPMStoreReason):
    #     if len(pmstore_reason.entry_list) == 0:
    #         return
    #     min_seq = min([x.op.seq for x in pmstore_reason.entry_list])
    #     max_seq = max([x.op.seq for x in pmstore_reason.entry_list])

    #     log_msg = "seq range of the pm stores: [%d, %d]" % (min_seq, max_seq)
    #     global_logger.debug(log_msg)

    #     # note, start seq is not included to be persist, such use min_seq for pre oracle
    #     self.pre_oracle_cp = CrashPlanEntry(CrashPlanType.PreOracle, min_seq, {}, {}, '')
    #     # note, start seq is not included to be persist, such use max_sqe + 1 for post oracle
    #     self.post_oracle_cp = CrashPlanEntry(CrashPlanType.PostOracle, max_seq + 1, {}, {}, '')


    def gen_cp_for_lsw(self,
                         lsw_reason : MechLSWReason,
                         pmstore_reason : MechPMStoreReason,
                         split_entry : OpTraceEntry) -> list:
        rst = []

        # for entry in lsw_reason.entry_list:
        #     entry : MechLSWEntry

        #     # one crash plan after lsw
        #     # do not persist other store if they are not a part of the LSW and in-flight with the last lsw update
        #     store_seq_list = [entry.tail_store.op.seq] + entry.get_safe_data_seq_list()
        #     min_store_seq = min(store_seq_list)
        #     max_store_seq = max(store_seq_list)
        #     pm_ops_list = split_entry.get_pm_ops_by_seq_range(min_store_seq, max_store_seq)
        #     pm_fence_list = [x[0] for x in pm_ops_list if x[0].type.isFenceTy()]
        #     pm_fence_seq_list = [x.seq for x in pm_fence_list]
        #     max_fence_seq_before = max(pm_fence_seq_list)
        #     tobe_persisted = [x for x in store_seq_list if x >= max_fence_seq_before]

        #     cp = CrashPlanEntry(CrashPlanType.LSWSafe, entry.tail_store.op.instid, max_fence_seq_before,
        #                         set(tobe_persisted), {}, entry.tail_store.op.to_result_str())
        #     rst.append(cp)

        return rst


    def gen_cp_for_rep(self,
                         rep_reason : MechReplReason,
                         pmstore_reason : MechPMStoreReason,
                         split_entry : OpTraceEntry) -> list:
        rst = []

        for entry in rep_reason.entry_list:
            entry : MechReplEntry
            min_seq = entry.store.op_st.seq
            safe_stores = entry.get_safe_data_seq_list()
            unsafe_stores = entry.get_unsafe_data_seq_list()
            if safe_stores or unsafe_stores:
                min_seq = min(safe_stores + unsafe_stores)

            # 1 crash at writing the primary
            if len(entry.src_update_stores) > 0:
                op = entry.src_update_stores[-1].op
                cp = CrashPlanEntry(CrashPlanType.RepSafe, op.instid, op.seq,
                                    {}, {}, op.to_result_str())
                rst.append(cp)

            # 2 crash at copying to the replica
            cp = CrashPlanEntry(CrashPlanType.RepSafe, entry.store.op_st.instid, entry.store.op_st.seq,
                                {}, {}, entry.store.op_st.to_result_str())
            rst.append(cp)

        return rst


    def gen_cp_for_undojnl(self,
                             undojnl_reason : MechUndoJnlReason,
                             pmstore_reason : MechPMStoreReason) -> list:
        rst = []

        for entry in undojnl_reason.entry_list:
            entry : MechUndoJnlEntry
            min_seq = entry.tail_store.op.seq
            safe_stores = entry.get_safe_entry_store_seq_list()
            unsafe_stores = entry.get_unsafe_entry_store_seq_list()
            if safe_stores or unsafe_stores:
                min_seq = min(safe_stores + unsafe_stores)

            # 1. crash plan for this mech before update the head to see if it can restore journaled items.
            if entry.head_store:
                cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, entry.head_store.op.instid, entry.head_store.op.seq,
                                    {}, {}, entry.tail_store.op.to_result_str())
                rst.append(cp)
            elif len(entry.jnl_inplace_stores) > 0:
                op = entry.jnl_inplace_stores[-1].op
                cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, op.instid, op.seq + 1,
                                    {}, {}, op.to_result_str())
                rst.append(cp)
            elif entry.cheat_sheet and not entry.cheat_sheet.is_pre_allocation:
                cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, entry.tail_store.op.instid, entry.tail_store.op.seq + 1,
                                    {}, {}, entry.tail_store.op.to_result_str())
                rst.append(cp)
            elif entry.cheat_sheet and entry.cheat_sheet.is_pre_allocation:
                op = entry.jnl_safe_stores[-1].op
                cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, op.instid, op.seq + 1,
                                    {}, {}, op.to_result_str())
                rst.append(cp)
            else:
                cp = CrashPlanEntry(CrashPlanType.UndojnlSafe, entry.tail_store.op.instid, entry.tail_store.op.seq + 1,
                                    {}, {}, entry.tail_store.op.to_result_str())
                rst.append(cp)

        return rst

    def gen_cp_for_oracle(self,
                          pmstore_reason : MechPMStoreReason,
                          split_entry : OpTraceEntry) -> list:
        if len(pmstore_reason.entry_list) == 0:
            return
        # min_seq = min([x.op.seq for x in pmstore_reason.entry_list])
        # max_seq = max([x.op.seq for x in pmstore_reason.entry_list])
        min_seq = split_entry.min_seq
        max_seq = split_entry.max_seq

        log_msg = "seq range of the pm stores: [%d, %d]" % (min_seq, max_seq)
        global_logger.debug(log_msg)

        # note, start seq is not included to be persist, such use min_seq for pre oracle
        self.pre_oracle_cp = CrashPlanEntry(CrashPlanType.PreOracle, -1, min_seq, {}, {}, '')
        # note, start seq is not included to be persist, such use max_sqe + 1 for post oracle
        self.post_oracle_cp = CrashPlanEntry(CrashPlanType.PostOracle, -1, max_seq + 1, {}, {}, '')


    def __regen_cp_for_non_atomic_write(self,
                                      cp : CrashPlanEntry,
                                      pmstore_entry :  MechPMStoreEntry,
                                      sampling_nonatomic_write : bool,
                                      nonatmic_as_single_write : bool) -> list:
        if nonatmic_as_single_write and \
                    (pmstore_entry.op.size >= 20 or
                     pmstore_entry.op.type.isMemTransStore() or
                     pmstore_entry.op.type.isMemset()):
            return [cp]
        elif pmstore_entry.op.size >= 20 or \
                (pmstore_entry.op.type.isMemset() or pmstore_entry.op.type.isMemTransStore()):
            tmp = []
            start_addr = pmstore_entry.op.addr
            end_addr = start_addr + pmstore_entry.op.size

            if start_addr//ATOMIC_WRITE_BYTES == end_addr//ATOMIC_WRITE_BYTES:
                # the copy or memset does not write to the space that exceeds the atomic size
                return [cp]

            while start_addr < end_addr:
                tmp_cp = copy.copy(cp)
                tmp_cp.sampling_type = CrashPlanSamplingType.SamplingAtomic
                tmp_cp.sampling_seq = pmstore_entry.op.seq
                tmp_cp.sampling_addr = start_addr
                tmp.append(tmp_cp)
                start_addr += ATOMIC_WRITE_BYTES

            if sampling_nonatomic_write and len(tmp) > 3:
                tmp[0].sampling_type = CrashPlanSamplingType.SamplingStart
                tmp[(len(tmp) - 1)//2].sampling_type = CrashPlanSamplingType.SamplingMid
                tmp[-1].sampling_type = CrashPlanSamplingType.SamplingEnd
                return [cp, tmp[0], tmp[(len(tmp) - 1)//2], tmp[-1]]
            else:
                return [cp] + tmp

        else:
            return [cp]

    def __gen_2cp_for_a_store(self,
                            pmstore_entry :  MechPMStoreEntry,
                            split_entry : OpTraceEntry,
                            sampling_nonatomic_write : bool,
                            nonatmic_as_single_write : bool,
                            consider_cl_prefix : bool) -> list:
        rst = []
        seq = pmstore_entry.op.seq

        # 1. persist unguarded write only among all in-flight writes
        # 1.1 find all persisted stores before the store
        min_cluster_num = min(split_entry.in_flight_seq_cluster_map[seq])
        seq_set = set([seq])
        for cluster_num, seqs in split_entry.in_flight_cluster_flushing_map.items():
            if cluster_num < min_cluster_num:
                seq_set |= set(seqs)
        # 1.2 add dep writes
        if seq in split_entry.write_dep_seq_map:
            dbg_msg = "seq (%d)'s dep seqs (%s), (%s)" % \
                (seq, str(split_entry.write_dep_seq_map[seq]), seq_set | split_entry.write_dep_seq_map[seq])
            global_logger.debug(dbg_msg)
            seq_set |= split_entry.write_dep_seq_map[seq]
        # 1.3 if consider the prefix before this store, all stores that in the same cache line and
        #     occurs before this store should be persisted:
        if consider_cl_prefix:
            lower_addr = alignToFloor(pmstore_entry.op.addr, CACHELINE_BYTES)
            upper_addr = pmstore_entry.op.addr + pmstore_entry.op.size
            if upper_addr % CACHELINE_BYTES != 0:
                upper_addr = alignToCeil(upper_addr, CACHELINE_BYTES)
            same_cl_stores = split_entry.get_pm_ops_by_addr_range(lower_addr, upper_addr)
            for store in same_cl_stores:
                store : TraceEntry
                if store.type.isStoreSeries() and (min(seq_set) < store.seq < seq) and (not store.is_nt_store):
                    seq_set.add(store.seq)

        # 1.4 create the cp entry
        dbg_msg = "persist itself: %d, and dep: %s, but no other seq." % (seq, str(seq_set))
        global_logger.debug(dbg_msg)
        cp = CrashPlanEntry(CrashPlanType.UnguardedPSelf, pmstore_entry.op.instid, min(seq_set), seq_set, {seq},
                            pmstore_entry.op.to_result_str())
        rst += self.__regen_cp_for_non_atomic_write(cp, pmstore_entry,
                                                    sampling_nonatomic_write,
                                                    nonatmic_as_single_write)

        # 2. persist all other in-flight writes except this unguarded write
        # 2.1 find all other will-be-flushed stores
        max_cluster_num = max(split_entry.in_flight_seq_cluster_map[seq])
        dbg_msg = "cluster number for %d: %d" % (seq, max_cluster_num)
        global_logger.debug(dbg_msg)
        seq_set = set()
        for cluster_num, seqs in split_entry.in_flight_cluster_flushing_map.items():
            if cluster_num <= max_cluster_num:
                seq_set |= set(seqs)
                dbg_msg = "add other inflight stores for %d: %d, %s" % (cluster_num, seq, set(seqs))
                global_logger.debug(dbg_msg)
        # 2.2. remove itself
        if seq in seq_set:
            seq_set.remove(seq)
        # 2.3 remove stores that deps on this store
        for other_seq in seq_set.copy():
            if other_seq > seq and \
                    other_seq in split_entry.write_dep_seq_map and \
                    seq in split_entry.write_dep_seq_map[other_seq]:
                seq_set.remove(other_seq)
                dbg_msg = "not persist itself remove dep seq: %d" % (other_seq)
                global_logger.debug(dbg_msg)
        # 1.3 if consider the prefix before this store, all stores that in the same cacheline and
        #     occurs after this should not be persisted:
        if consider_cl_prefix:
            lower_addr = alignToFloor(pmstore_entry.op.addr, CACHELINE_BYTES)
            upper_addr = pmstore_entry.op.addr + pmstore_entry.op.size
            if upper_addr % CACHELINE_BYTES != 0:
                upper_addr = alignToCeil(upper_addr, CACHELINE_BYTES)
            same_cl_stores = split_entry.get_pm_ops_by_addr_range(lower_addr, upper_addr)
            for store in same_cl_stores:
                store : TraceEntry
                if store.type.isStoreSeries() and (store.seq > seq) and (not store.is_nt_store):
                    if store.seq in seq_set:
                        seq_set.remove(store.seq)

        dbg_msg = "persist all other seq: %s but not itself: %d" % (str(seq_set), seq)
        global_logger.debug(dbg_msg)
        # 2.4 create the cp entry
        min_seq = seq if len(seq_set) == 0 else min(seq, min(seq_set))
        cp = CrashPlanEntry(CrashPlanType.UnguardedPOther, pmstore_entry.op.instid, min_seq, seq_set, {seq},
                            pmstore_entry.op.to_result_str())
        rst += self.__regen_cp_for_non_atomic_write(cp, pmstore_entry,
                                                    sampling_nonatomic_write,
                                                    nonatmic_as_single_write)

        # 3. return
        return rst


    def __gen_comb_for_a_set_stores(self,
                                   inflight_store_seq_set : set,
                                   last_fenced_store_seq : int,
                                   pmstore_reason : MechPMStoreReason,
                                   split_entry : OpTraceEntry,
                                   sampling_nonatomic_write : bool,
                                   ignore_mem_copy_set : bool,
                                   nonatmic_as_single_write : bool,
                                   plus_one : bool) -> list:
        """No real crash plans will be generated due to the huge number"""
        nonatomic_store_list = []
        entry_list = []
        for seq in inflight_store_seq_set:
            pmstore_entry : MechPMStoreEntry = pmstore_reason.get_entry_by_seq(seq)
            pmstore_entry = pmstore_entry[0]
            if nonatmic_as_single_write and \
                    (pmstore_entry.op.size >= 20 or
                     pmstore_entry.op.type.isMemTransStore() or
                     pmstore_entry.op.type.isMemset()):
                nonatomic_store_list.append(pmstore_entry)
            else:
                entry_list.append(pmstore_entry.op)

        cache = WitcherCache(EmptyBinaryFile())
        atomic_ops = convert_entry_list_with_sampling_option(entry_list, sampling_nonatomic_write, ignore_mem_copy_set)
        atomic_ops.sort(key=lambda x:x.seq)
        reorder_simulator = ReorderSimulator(cache, consider_ow=True)

        # insert fenced op first
        for op in atomic_ops:
            if op.seq <= last_fenced_store_seq:
                cache.accept(op)

        # insert the fence
        fence_op = Fence(last_fenced_store_seq + 1)
        cache.accept(fence_op)

        # insert other in-flight stores
        for op in atomic_ops:
            if op.seq > last_fenced_store_seq:
                cache.accept(op)

        # get the reorder number
        num_combinations, _, _ = reorder_simulator.get_reorder_nums()
        if plus_one:
            # add C_n^0 case
            num_combinations += 1

        # if time_two and num_combinations > 0:
        #     # considering the rest of stores in the same in-flight cluster as one write
        #     # thus, it has 2 combinations
        #     num_combinations *= 2

        # We cannot compute the exactly number of the combination since
        # the nonatomic stores cannot be added to the simulated cache.
        # Thus, we compute the number roughly if nonatomic stores as one single write.
        if len(nonatomic_store_list) > 0:
            num_combinations = num_combinations * (2 ** len(nonatomic_store_list))

        # construct the crash plans
        cp = CrashPlanEntry(CrashPlanType.Unguarded, -1, 0, {}, {}, 'no_pickle')
        cp.num_cp_entries = num_combinations

        dbg_msg = "generated %d comb crash plans for %s with last fence seq %d" % (num_combinations, str(entry_list), last_fenced_store_seq)
        global_logger.debug(dbg_msg)

        # return
        return [cp]


    def gen_cp_2cp(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               sampling_nonatomic_write : bool,
               ignore_mem_copy_set : bool,
               nonatmic_as_single_write : bool,
               consider_cl_prefix : bool) -> {list, list}:
        """Tow crash plans for all stores"""
        # for debugging
        num_reordered_records = []
        num_2cp_stores = 0
        rst = []
        pmstore_set = [x for x in pmstore_reason.entry_list]

        visited_cps = set()

        for pmstore_entry in pmstore_set:
            pmstore_entry : MechPMStoreEntry

            if ignore_mem_copy_set and (pmstore_entry.op.type.isMemset() or pmstore_entry.op.type.isMemTransStore()):
                dbg_msg = "entry %d, %s, %d is memory copy or set, ignore it." % (pmstore_entry.op.seq, hex(pmstore_entry.op.addr), pmstore_entry.op.size)
                global_logger.debug(dbg_msg)
                continue

            # check if the in-flight cluster only has one (itself) store
            if pmstore_entry.op.seq not in split_entry.in_flight_seq_cluster_map:
                # no such record!
                err_msg = "seq not in in-flight cluster map: %s, %s" % (str(pmstore_entry), str(split_entry.in_flight_seq_cluster_map))
                global_logger.error(err_msg)
                assert False, err_msg

            # cluster_num_list = split_entry.in_flight_seq_cluster_map[pmstore_entry.op.seq]
            # for cluster_num in cluster_num_list:
            #     inflight_store_set = set(split_entry.in_flight_cluster_seq_map[cluster_num])
            #     if len(inflight_store_set) == 1:
            #         dbg_msg = "only one store in the in-flight cluster, %s, %s" % (str(pmstore_entry), str(split_entry.in_flight_seq_cluster_map))
            #         global_logger.debug(dbg_msg)
                    # keep to generate 2cp for this write
                    # continue
            num_2cp_stores += 1

            generated_cps = self.__gen_2cp_for_a_store(pmstore_entry, split_entry, \
                                                        sampling_nonatomic_write,
                                                        nonatmic_as_single_write,
                                                        consider_cl_prefix)

            dbg_msg = "gen_cp_2cp: %d cps generated for %d before filter visited cps\n" % (len(generated_cps), pmstore_entry.op.seq)
            global_logger.debug(dbg_msg)

            new_generated_cps = []
            for cp in generated_cps:
                cp : CrashPlanEntry
                if cp.num_cp_entries == 1:
                    start_seq = frozenset({cp.start_seq})
                    persisted_seqs = frozenset(cp.persist_seqs)
                    sampling_keys = frozenset({0})
                    if cp.sampling_type != CrashPlanSamplingType.SamplingNone and \
                            cp.sampling_seq != None and cp.sampling_addr != None:
                        sampling_keys = frozenset({cp.sampling_seq, cp.sampling_addr})
                    set_key = frozenset({start_seq, persisted_seqs, sampling_keys})
                    if set_key not in visited_cps:
                        new_generated_cps.append(cp)
                        visited_cps.add(set_key)
                else:
                    new_generated_cps.append(cp)

            dbg_msg = "## gen_cp_2cp: %d cps generated for %d\n" % (len(new_generated_cps), pmstore_entry.op.seq)
            global_logger.debug(dbg_msg)
            self.dump_data += dbg_msg

            rst += new_generated_cps
                # break

        num_reordered_records.append(num_2cp_stores)
        return rst, num_reordered_records


    def gen_cp_mech_2cp(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               lsw_reason : MechLSWReason,
               rep_reason : MechReplReason,
               undojnl_reason : MechUndoJnlReason,
               sampling_nonatomic_write : bool,
               ignore_mem_copy_set : bool,
               nonatmic_as_single_write : bool,
               consider_cl_prefix : bool) -> {list, list}:
        rst = []
        # for debugging
        num_reordered_records = [0, 0, 0, 0]

        # 1. for lsw
        if lsw_reason:
            rst += self.gen_cp_for_lsw(lsw_reason, pmstore_reason, split_entry)
            num_reordered_records[0] = len(lsw_reason.entry_list)

        # 2. for replication
        if rep_reason:
            rst += self.gen_cp_for_rep(rep_reason, pmstore_reason, split_entry)
            num_reordered_records[1] = len(rep_reason.entry_list)

        # 3. for undo journal
        if undojnl_reason:
            rst += self.gen_cp_for_undojnl(undojnl_reason, pmstore_reason)
            num_reordered_records[2] = len(undojnl_reason.entry_list)

        # 4. for unprotected stores
        guarded_seqs = []
        if lsw_reason:
            for entry in lsw_reason.entry_list:
                guarded_seqs += entry.get_opid_seq_list()
                guarded_seqs += entry.get_safe_data_seq_list()
                guarded_seqs += entry.get_unsafe_data_seq_list()
        if rep_reason:
            for entry in rep_reason.entry_list:
                guarded_seqs += entry.get_opid_seq_list()
                guarded_seqs += entry.get_safe_data_seq_list()
                guarded_seqs += entry.get_unsafe_data_seq_list()
        if undojnl_reason:
            for entry in undojnl_reason.entry_list:
                guarded_seqs += entry.get_opid_seq_list()
                guarded_seqs += entry.get_safe_data_seq_list()
                guarded_seqs += entry.get_unsafe_data_seq_list()

        guarded_seqs = set(guarded_seqs)
        unguarded_seqs = set([x.op.seq for x in pmstore_reason.entry_list])
        unguarded_seqs = list(unguarded_seqs - guarded_seqs)
        unguarded_seqs.sort()

        num_reordered_records[3] = len(unguarded_seqs)

        visited_cps = set()
        for seq in unguarded_seqs:
            pmstore_entry : MechPMStoreEntry = pmstore_reason.get_entry_by_seq(seq)
            pmstore_entry = pmstore_entry[0]

            if ignore_mem_copy_set and (pmstore_entry.op.type.isMemset() or pmstore_entry.op.type.isMemTransStore()):
                dbg_msg = "entry %d, %s, %d is memory copy or set, ignore it." % (pmstore_entry.op.seq, hex(pmstore_entry.op.addr), pmstore_entry.op.size)
                global_logger.debug(dbg_msg)
                continue

            # check if the in-flight cluster only has one (itself) store
            if pmstore_entry.op.seq not in split_entry.in_flight_seq_cluster_map:
                # no such record!
                err_msg = "seq not in in-flight cluster map: %s, %s" % (str(pmstore_entry), str(split_entry.in_flight_seq_cluster_map))
                global_logger.error(err_msg)
                assert False, err_msg

            # cluster_num_list = split_entry.in_flight_seq_cluster_map[pmstore_entry.op.seq]
            # for cluster_num in cluster_num_list:
            #     inflight_store_set = set(split_entry.in_flight_cluster_seq_map[cluster_num])
            #     if len(inflight_store_set) == 1:
            #         dbg_msg = "only one store in the in-flight cluster, %s, %s" % (str(pmstore_entry), str(split_entry.in_flight_seq_cluster_map))
            #         global_logger.debug(dbg_msg)
                    # keep to generate 2cp for this write
                    # continue

            generated_cps = self.__gen_2cp_for_a_store(pmstore_entry, split_entry,
                                                        sampling_nonatomic_write,
                                                        nonatmic_as_single_write,
                                                        consider_cl_prefix)

            dbg_msg = "gen_cp_mech_2cp: %d cps generated for %d before filter visited cps\n" % (len(generated_cps), pmstore_entry.op.seq)
            global_logger.debug(dbg_msg)

            new_generated_cps = []
            for cp in generated_cps:
                if cp.num_cp_entries == 1:
                    start_seq = frozenset({cp.start_seq})
                    persisted_seqs = frozenset(cp.persist_seqs)
                    sampling_keys = frozenset({0})
                    if cp.sampling_type != CrashPlanSamplingType.SamplingNone and \
                            cp.sampling_seq != None and cp.sampling_addr != None:
                        sampling_keys = frozenset({cp.sampling_seq, cp.sampling_addr})
                    set_key = frozenset({start_seq, persisted_seqs, sampling_keys})
                    if set_key not in visited_cps:
                        new_generated_cps.append(cp)
                        visited_cps.add(set_key)
                else:
                    new_generated_cps.append(cp)

            dbg_msg = "## gen_cp_mech_2cp: %d cps generated for %d\n" % (len(new_generated_cps), pmstore_entry.op.seq)
            global_logger.debug(dbg_msg)
            self.dump_data += dbg_msg

            rst += new_generated_cps
                # break

        return rst, num_reordered_records


    def gen_cp_mech_comb(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               lsw_reason : MechLSWReason,
               rep_reason : MechReplReason,
               undojnl_reason : MechUndoJnlReason,
               sampling_nonatomic_write : bool,
               ignore_mem_copy_set : bool,
               nonatmic_as_single_write : bool) -> {list, list}:
        """No valid crash plan entries generated since the number is huge"""
        rst = []
        # for debugging
        num_reordered_records = [0, 0, 0, []]

        # 1. for lsw
        if lsw_reason:
            rst += self.gen_cp_for_lsw(lsw_reason, pmstore_reason, split_entry)
            num_reordered_records[0] = len(lsw_reason.entry_list)

        # 2. for replication
        if rep_reason:
            rst += self.gen_cp_for_rep(rep_reason, pmstore_reason, split_entry)
            num_reordered_records[1] = len(rep_reason.entry_list)

        # 3. for undo journal
        if undojnl_reason:
            rst += self.gen_cp_for_undojnl(undojnl_reason, pmstore_reason)
            num_reordered_records[2] = len(undojnl_reason.entry_list)

        # 4. for unprotected stores
        guarded_seqs = []
        if lsw_reason:
            for entry in lsw_reason.entry_list:
                guarded_seqs += entry.get_opid_seq_list()
                guarded_seqs += entry.get_safe_data_seq_list()
                guarded_seqs += entry.get_unsafe_data_seq_list()
        if rep_reason:
            for entry in rep_reason.entry_list:
                guarded_seqs += entry.get_opid_seq_list()
                guarded_seqs += entry.get_safe_data_seq_list()
                guarded_seqs += entry.get_unsafe_data_seq_list()
        if undojnl_reason:
            for entry in undojnl_reason.entry_list:
                guarded_seqs += entry.get_opid_seq_list()
                guarded_seqs += entry.get_safe_data_seq_list()
                guarded_seqs += entry.get_unsafe_data_seq_list()

        guarded_seqs = set(guarded_seqs)
        unguarded_seqs = set([x.op.seq for x in pmstore_reason.entry_list])
        unguarded_seqs = list(unguarded_seqs - guarded_seqs)
        unguarded_seqs.sort()
        unguarded_seqs_set = set(unguarded_seqs)

        last_fenced_store_seq : int = 0
        global_logger.debug("split_entry.in_flight_cluster_seq_map: %s" % (str(split_entry.in_flight_cluster_seq_map)))
        for cluster_num, inflight_store_list in sorted(split_entry.in_flight_cluster_seq_map.items()):
            global_logger.debug("cluster number: %d" % (cluster_num))
            inflight_store_seq_set = set(inflight_store_list) & unguarded_seqs_set
            if len(inflight_store_seq_set) == 0:
                continue

            num_reordered_records[3].append(len(inflight_store_seq_set))
            generated_cps = self.__gen_comb_for_a_set_stores(inflight_store_seq_set, last_fenced_store_seq,
                                                             pmstore_reason, split_entry,
                                                             sampling_nonatomic_write,
                                                             ignore_mem_copy_set,
                                                             nonatmic_as_single_write,
                                                             plus_one=True)

            num_comb_cps = sum([x.num_cp_entries for x in generated_cps])
            dbg_msg = "## gen_cp_mech_comb: %d cps generated for a set of stores %d\n" % (num_comb_cps, len(inflight_store_seq_set))
            global_logger.debug(dbg_msg)
            self.dump_data += dbg_msg

            rst += generated_cps
            last_fenced_store_seq = max(inflight_store_list)

        return rst, num_reordered_records


    """
    Chipmunk:
    1. Cannot trace assembly code (e.g., CAS, Xchg)
    2. Cannot trace temporal stores (e.g., assignment)
    3. Traces nt_memcpy through file systems' centralized functions
    4. Traces writes through file systems' centralized persistence (flush) functions
    5. Coalesces logically-related non-temporal stores and flushes
       (since Chipmunk do not know stores, it coalesces flushes)
    6. Reorders cache lines only except non-temporal stores.
    7. Considers non-temporal stores the data write. The variable in their implementation is "likely_data".
    Since we can trace at a fine granularity, instructions and assembly,
    while the flush instruction does not have a size to indicate the writes,
    we follow Chipmunk's scheme, but with a different implementation on Silhouette:
    1. Traces everything we can trace
    2. Coalesces logically-related both temporal stores and non-temporal stores
    3. Reorders cache lines.
    4. ignore_xxx means these stores are directly excluded from this scheme
    5. cache_xxx means these stores are splitted into atomic stores and
       cached in cache and will be reordered with cache lines.
       Otherwise, they will be considered a single write instead of cached in cache.
       **cache_nt_stores** must be false since **nt_store** cannot be cached.
    6. If the write size is larger then not_cache_size_threshold, they won't be cached.
       In Chipmunk, this size is 5 * cache line size
       Like what Chipmunk did: https://github.com/utsaslab/chipmunk/blob/main/chipmunk/loggers/logger-nova.c#L457
    This scheme, cachelinereordering, is similar to Chipmunk's scheme.
    Chipmunk also does the cache-line level reordering since it divide flushes to cache-line size:
    https://github.com/utsaslab/chipmunk/blob/main/chipmunk/loggers/logger-nova.c#L560
    """
    def gen_cp_cachelinereordering_scheme(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               ignore_nt_stores : bool,
               ignore_data_stores : bool,
               ignore_copy_stores : bool,
               ignore_set_stores : bool,
               cache_nt_stores : bool, # must be **false**
               cache_data_stores : bool,
               cache_copy_stores : bool,
               cache_set_stores : bool,
               not_cache_size_threshold : int,
               not_cached_store_coalesce : bool,
               no_real_cp : bool) -> {list, list}:
        cp_list = []
        # for debugging
        num_reordered_records = []
        # 1. distinguish stores
        #    Following Chipmunk, we also coalesce logically-related nt or data or copy or set stores
        #    Cached store could be store, flush, and fence
        #    Other stores must be store
        cached_store_list = []
        other_store_list = []
        other_store_seq_list = []
        user_data_store_seq_list = split_entry.user_space_trans_load_seq_entry_map.keys()
        user_data_store_seq_list = [x+1 for x in user_data_store_seq_list]
        last_store_seq = 0
        last_store_upper_boundary = 0

        for seq, entry_list in sorted(split_entry.pm_seq_entry_map.items()):
            tobe_added_other_store = None
            if entry_list[0].is_nt_store:
                if ignore_nt_stores:
                    continue
                else:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].seq in user_data_store_seq_list:
                if ignore_data_stores:
                    continue
                elif not cache_data_stores:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].type.isMemTransStore():
                if ignore_copy_stores:
                    continue
                elif not cache_copy_stores:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].type.isMemset():
                if ignore_set_stores:
                    continue
                elif not cache_set_stores:
                    tobe_added_other_store = entry_list[0]
            if not_cache_size_threshold != None and \
                    entry_list[0].type.isStoreSeries() and \
                    entry_list[0].size > not_cache_size_threshold:
                tobe_added_other_store = entry_list[0]

            if tobe_added_other_store:
                if not_cached_store_coalesce and \
                        len(other_store_list) > 0 and \
                        last_store_seq == other_store_list[-1] and \
                        last_store_upper_boundary == tobe_added_other_store.addr:
                    # coalesce logically-related stores
                    other_store_list[-1].append(tobe_added_other_store)
                    other_store_seq_list[-1].append(tobe_added_other_store.seq)
                else:
                    other_store_list.append([tobe_added_other_store])
                    other_store_seq_list.append([tobe_added_other_store.seq])
                last_store_seq = tobe_added_other_store.seq
                last_store_upper_boundary = tobe_added_other_store.addr + tobe_added_other_store.size
            else:
                cached_store_list.append(entry_list[0])
                last_store_seq = entry_list[0].seq
                last_store_upper_boundary = entry_list[0].addr + entry_list[0].size

        global_logger.debug(str(cached_store_list))
        global_logger.debug(str(other_store_list))
        # cached_store_list.sort(key=lambda x : x.seq)
        # other_store_list.sort(key=lambda x : x[0].seq)
        # other_store_seq_list.sort(key=lambda x : x[0])

        # 2. simulate a cache
        cache = WitcherCache(EmptyBinaryFile())
        atomic_ops = convert_entry_list_with_sampling_option(cached_store_list, sampling_nonatomic_write=False, ignore_mem_copy_set=False)
        atomic_ops.sort(key=lambda x:x.seq)

        # 3. simulating stores
        last_fence_seq = 0 if len(atomic_ops) == 0 else atomic_ops[0].seq - 1
        for op in atomic_ops:
            if isinstance(op, Store):
                cache.accept(op)
            elif isinstance(op, Flush):
                cache.accept(op)
            elif isinstance(op, Fence):
                cacheline_seq_list = []
                for cacheline in cache.get_cachelines():
                    if len(cacheline.stores_list) > 0:
                        cacheline_seq_list.append([x.seq for x in cacheline.stores_list])
                global_logger.debug(str(cacheline_seq_list))

                could_reordered_seq_list = []
                for tu in other_store_seq_list:
                    tmp = []
                    for seq in tu:
                        if last_fence_seq < seq < op.seq:
                            tmp.append(seq)
                    if len(tmp) > 0:
                        could_reordered_seq_list.append(tmp)
                global_logger.debug(str(could_reordered_seq_list))

                num_reordered_records.append([])
                num_reordered_records[-1].append(len(cacheline_seq_list))
                num_reordered_records[-1].append(len(could_reordered_seq_list))

                could_reordered_seq_list += cacheline_seq_list
                if len(could_reordered_seq_list) > 0:
                    if not no_real_cp:
                        for i in range(1, len(could_reordered_seq_list) + 1):
                            for comb_case in combinations(could_reordered_seq_list, i):
                                tobe_persisted = []
                                for tu in comb_case:
                                    tobe_persisted += tu
                                cp = CrashPlanEntry(CrashPlanType.CacheLineReordering, \
                                                    -1, last_fence_seq,
                                                    set(tobe_persisted), set(tobe_persisted),
                                                    "CacheLineReordering")
                                cp_list.append(cp)
                    else:
                        cp = CrashPlanEntry(CrashPlanType.CacheLineReordering, -1, 0, {}, {}, 'no_pickle')
                        cp.num_cp_entries = 2**len(could_reordered_seq_list) - 1
                        cp_list.append(cp)
                        dbg_msg = "CacheLineReordering scheme number cps: %d" % (cp.num_cp_entries)
                        global_logger.debug(dbg_msg)

                last_fence_seq = op.seq
                cache.accept(op)
                cache.write_back_all_flushing_stores()
                cache.write_back_all_persisted_stores()
            else:
                assert False, "invalid op type, %s, %s" % (type(op), str(op))

        return cp_list, num_reordered_records


    def gen_cp_cachelineChipmunk_scheme(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               not_cache_size_threshold : int,
               no_real_cp : bool) -> {list, list}:
        cp_list = []
        # split_entry.init_pm_entries()
        # dbg_msg = "after split pm entries are\n%s\n%s" % (str(split_entry.seq_entry_map), str(split_entry.pm_seq_entry_map))
        # global_logger.debug(dbg_msg)
        # for debugging
        num_reordered_records = []
        # 1. distinguish stores
        #    Following Chipmunk, we also coalesce logically-related nt or data or copy or set stores
        #    Cached store could be store, flush, and fence
        #    Other stores must be store
        write_list = []
        for seq, entry_list in sorted(split_entry.seq_entry_map.items()):
            entry : TraceEntry = entry_list[0]
            if len(write_list) == 0:
                write_list.append([]) # one fence point
            if entry.type.isImpFenceTy():
                # Chipmunk cannot see implicit fence
                continue
            if entry.type.isFenceTy():
                # Chipmunk can see other fences
                write_list.append([]) # one fence point
            if entry.type.isMemTransStore() or entry.type.isMemset():
                if entry.is_nt_store and \
                        entry.addr >= split_entry.pm_addr and entry.addr + entry.size <= split_entry.pm_addr + split_entry.pm_size:
                    # Chipmunk can only see nt_memcpy
                    write_list[-1].append(entry)
            if entry.type.isCentflush():
                if entry.addr >= split_entry.pm_addr and entry.addr + entry.size <= split_entry.pm_addr + split_entry.pm_size:
                    # Chipmunk consider the flush is write
                    write_list[-1].append(entry)

        # 2. coalesce writes if they are logically related
        new_write_list = []
        for fence_point in write_list:
            new_write_list.append([])
            last_write = None
            for write in fence_point:
                if last_write != None and \
                        last_write.addr + last_write.size == write.addr:
                    new_write_list[-1][-1].append(write)
                else:
                    new_write_list[-1].append([])
                    new_write_list[-1][-1].append(write)
                last_write = write
        write_list = new_write_list

        # 3. Distingush cached and not cached writes
        def can_see_store_trace(trace : TraceEntry) -> bool:
            if not trace.type.isStoreSeries():
                return False
            if trace.type.isMemTransStore() or trace.type.isMemset():
                if trace.is_nt_store:
                    return True
            elif not trace.is_nt_store:
                return True
            return False
        not_cached_writes = []
        not_cached_write_seqs = []
        cached_writes = []
        cached_write_seqs = []
        flushed_fenced_write_seqs = set()
        for fence_point in write_list:
            not_cached_writes.append([])
            not_cached_write_seqs.append([])
            cached_writes.append([])
            cached_write_seqs.append([])
            for contiguous_writes in fence_point:
                size = sum([x.size for x in contiguous_writes])
                if size >= not_cache_size_threshold:
                    seq1 = split_entry.min_seq
                    seq2 = min([x.seq for x in contiguous_writes])
                    addr1 = min([x.addr for x in contiguous_writes])
                    addr2 = max([x.addr + x.size for x in contiguous_writes])
                    trace_entries = split_entry.get_pm_ops_by_seq_addr_range(seq1, seq2, addr1, addr2)
                    trace_entries = [x for x in trace_entries if x.type.isStoreSeries()]
                    trace_entries.sort(key = lambda x : x.seq)
                    dbg_msg = "convert writes to entries: %d, %d, 0x%x, 0x%x, %s, %s" % (seq1, seq2, addr1, addr2, str(contiguous_writes), str(trace_entries))
                    # global_logger.debug(dbg_msg)
                    if len(trace_entries) == 0:
                        global_logger.error("trace_entries is empty!\n" + dbg_msg + "\n" + str(split_entry.pm_seq_entry_map) + "\n" + str(split_entry.seq_entry_map))
                    new_trace_entries = []
                    for trace in trace_entries:
                        if can_see_store_trace(trace) and trace.seq not in flushed_fenced_write_seqs:
                            new_trace_entries.append(trace)
                            flushed_fenced_write_seqs.add(trace.seq)
                    dbg_msg = "filter out Chipmunk cannot see traces: %s, %s" % (str(trace_entries), str(new_trace_entries))
                    # global_logger.debug(dbg_msg)
                    if len(new_trace_entries) == 0:
                        global_logger.info("new_trace_entries is empty!\n" + dbg_msg)
                    trace_entries = new_trace_entries
                    not_cached_writes[-1].append(trace_entries)
                    not_cached_write_seqs[-1].append([x.seq for x in trace_entries])
                else:
                    # 4. split cached write as cache line sized
                    lower_addr = contiguous_writes[0].addr
                    upper_addr = contiguous_writes[-1].addr + contiguous_writes[-1].size
                    while lower_addr < upper_addr:
                        tmp = []
                        for write in contiguous_writes:
                            if isOverlapping([lower_addr, alignToCeil(lower_addr, CACHELINE_BYTES) - 1], [write.addr, write.addr + write.size]):
                                tmp.append(write)
                        if len(tmp) > 0:
                            seq1 = split_entry.min_seq
                            seq2 = min([x.seq for x in tmp])
                            addr1 = min([x.addr for x in tmp])
                            addr2 = max([x.addr + x.size for x in tmp])
                            trace_entries = split_entry.get_pm_ops_by_seq_addr_range(seq1, seq2, addr1, addr2)
                            trace_entries = [x for x in trace_entries if x.type.isStoreSeries()]
                            trace_entries.sort(key = lambda x : x.seq)
                            dbg_msg = "convert writes to entries: %d, %d, %x, %x, %s, %s" % (seq1, seq2, addr1, addr2, str(tmp), str(trace_entries))
                            if len(trace_entries) == 0:
                                global_logger.error("trace_entries is empty!\n" + dbg_msg + "\n" + str(split_entry.pm_seq_entry_map) + "\n" + str(split_entry.seq_entry_map))
                            new_trace_entries = []
                            for trace in trace_entries:
                                if can_see_store_trace(trace) and trace.seq not in flushed_fenced_write_seqs:
                                    new_trace_entries.append(trace)
                                    flushed_fenced_write_seqs.add(trace.seq)
                            dbg_msg = "filter out Chipmunk cannot see traces: %s, %s" % (str(trace_entries), str(new_trace_entries))
                            global_logger.debug(dbg_msg)
                            if len(trace_entries) == 0:
                                global_logger.info("new_trace_entries is empty!\n" + dbg_msg)
                            cached_writes[-1].append(trace_entries)
                            cached_write_seqs[-1].append([x.seq for x in trace_entries])
                        lower_addr = alignToCeil(lower_addr, CACHELINE_BYTES)

        global_logger.debug(str(cached_writes))
        global_logger.debug(str(not_cached_writes))
        assert len(not_cached_writes) == len(cached_writes), "mismatched fence points, %s, %s" % (str(cached_writes), str(not_cached_writes))

        # 4. simulating storing
        last_write_seq = split_entry.min_seq
        for i in range(len(cached_write_seqs)):
            fence_cached_write_seqs = cached_write_seqs[i]
            fence_not_cached_write_seqs = not_cached_write_seqs[i]
            could_reordered_seq_list = fence_cached_write_seqs + fence_not_cached_write_seqs

            num_reordered_records.append(could_reordered_seq_list)

            if len(could_reordered_seq_list) == 0:
                continue

            visited_seqs = set()
            if not no_real_cp:
                for i in range(1, len(could_reordered_seq_list) + 1):
                    for comb_case in combinations(could_reordered_seq_list, i):
                        tobe_persisted = []
                        for tu in comb_case:
                            tobe_persisted += tu
                        if len(tobe_persisted) == 0:
                            dbg_msg = "tobe_persisted is empty. fence_cached_write_seqs: %s;fence_not_cached_write_seqs: %s" % (str(fence_cached_write_seqs), str(fence_not_cached_write_seqs))
                            global_logger.debug(dbg_msg)

                        if frozenset(tobe_persisted) in visited_seqs:
                            continue
                        visited_seqs.add(frozenset(tobe_persisted))

                        cp = CrashPlanEntry(CrashPlanType.Chipmunk, \
                                            -1, last_write_seq,
                                            set(tobe_persisted), set(tobe_persisted),
                                            "Chipmunk")
                        cp_list.append(cp)
            else:
                cp = CrashPlanEntry(CrashPlanType.Chipmunk, -1, 0, {}, {}, 'no_pickle')
                cp.num_cp_entries = 2**len(could_reordered_seq_list) - 1
                cp_list.append(cp)
                dbg_msg = "Chipmunk scheme number cps: %d" % (cp.num_cp_entries)
                global_logger.debug(dbg_msg)
            for write_seq_list in could_reordered_seq_list:
                if len(write_seq_list) > 0:
                    last_write_seq = max(last_write_seq, max([x for x in write_seq_list])) + 1

        return cp_list, num_reordered_records


    """
    This scheme is similar to Vinter:
    1. reordering cache lines
    2. prefix-based oredering of stores
    3. ignore_xxx means these stores are directly excluded from this scheme.
       If do not ignore the store, data stores, copy stores, and set stores
       will be splitted into atomic stores and cached in the cache, and obey
       the prefix-based reordering. NT stores will not be cached and reordered
       with cache lines.
    4. cache_xxx means these stores are splitted into atomic stores and stored in cache.
       NT stores cannot be cached.
    5. If not_cached_store_as_single is true, we consider not cached stores
       (e.g., nt store, memcpy, memset) are a single write,
       which will not be splitted into atomic stores.
       Otherwise, we split it into atomic stores. This might generate a huge amount
       of crash plans.
    6. Currently, we do not generate real crash plans even if no_real_cp is true.
       This is because the number of crash plans is too huge to generate and test.
    """
    def gen_cp_prefixreordering_scheme(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               ignore_nt_stores : bool,
               ignore_data_stores : bool,
               ignore_copy_stores : bool,
               ignore_set_stores : bool,
               cache_nt_stores : bool, # must be **false**
               cache_data_stores : bool,
               cache_copy_stores : bool,
               cache_set_stores : bool,
               not_cache_size_threshold : int,
               not_cached_store_as_single : bool,
               no_real_cp : bool) -> {list, list}:
        cp_list = []
        # for debugging
        num_reordered_records = []
        # 1. distinguish stores
        cached_store_list = []
        other_store_list = []
        other_store_seq_list = []
        user_data_store_seq_list = split_entry.user_space_trans_load_seq_entry_map.keys()
        user_data_store_seq_list = [x+1 for x in user_data_store_seq_list]

        for seq, entry_list in sorted(split_entry.pm_seq_entry_map.items()):
            tobe_added_other_store = None
            if entry_list[0].is_nt_store:
                if ignore_nt_stores:
                    continue
                else:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].seq in user_data_store_seq_list:
                if ignore_data_stores:
                    continue
                elif not cache_data_stores:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].type.isMemTransStore():
                if ignore_copy_stores:
                    continue
                elif not cache_copy_stores:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].type.isMemset():
                if ignore_set_stores:
                    continue
                elif not cache_set_stores:
                    tobe_added_other_store = entry_list[0]
            if not_cache_size_threshold != None and \
                    entry_list[0].type.isStoreSeries() and \
                    entry_list[0].size > not_cache_size_threshold:
                tobe_added_other_store = entry_list[0]

            if tobe_added_other_store:
                other_store_list.append(tobe_added_other_store)
                other_store_seq_list.append(tobe_added_other_store.seq)
            else:
                cached_store_list.append(entry_list[0])

        global_logger.debug(str(cached_store_list))
        global_logger.debug(str(other_store_list))

        # 2. simulate a cache
        cache = WitcherCache(EmptyBinaryFile())
        atomic_ops = convert_entry_list_with_sampling_option(cached_store_list, sampling_nonatomic_write=False, ignore_mem_copy_set=False)
        atomic_ops.sort(key=lambda x:x.seq)

        # 3. simulating stores
        last_fence_seq = 0 if len(atomic_ops) == 0 else atomic_ops[0].seq - 1
        for op in atomic_ops:
            if isinstance(op, Store):
                cache.accept(op)
            elif isinstance(op, Flush):
                cache.accept(op)
            elif isinstance(op, Fence):
                cacheline_level_seq_list = []
                for cacheline in cache.get_cachelines():
                    if len(cacheline.stores_list) > 0:
                        cacheline_level_seq_list.append([x.seq for x in cacheline.stores_list])
                global_logger.debug(str(cacheline_level_seq_list))

                for store in other_store_list:
                    tmp = []
                    if not (last_fence_seq < store.seq < op.seq):
                        continue
                    if not_cached_store_as_single:
                        tmp.append({store.seq, store.addr, store.size})
                    else:
                        for split_addr in range(store.addr, store.addr + store.size, ATOMIC_WRITE_BYTES):
                            split_size = store.addr + store.size - split_addr
                            split_size = split_size if split_size < ATOMIC_WRITE_BYTES else ATOMIC_WRITE_BYTES
                            tmp.append([store.seq, split_addr, split_size])
                    if len(tmp) > 0:
                        cacheline_level_seq_list.append(tmp)

                num_reordered_records.append(cacheline_level_seq_list)

                # since cache lines are not too much, we can generate directly.
                if len(cacheline_level_seq_list) > 0:
                    total_cps = 0
                    if no_real_cp:
                        for i in range(1, len(cacheline_level_seq_list)+1):
                            for comb_case in combinations(cacheline_level_seq_list, i):
                                num_cps = 1
                                for seq_list in comb_case:
                                    # prefix-based reordering generates N cases,
                                    # where N is the number of elements in the list.
                                    num_cps *= len(seq_list)
                                total_cps += num_cps
                        cp = CrashPlanEntry(CrashPlanType.PrefixReordering, -1, 0, {}, {}, 'no_pickle')
                        cp.num_cp_entries = total_cps
                        cp_list.append(cp)
                        dbg_msg = "PrefixReordering scheme number cps: %d" % (cp.num_cp_entries)
                        global_logger.debug(dbg_msg)
                    else:
                        assert False, "PrefixReordering does not support to construct and test real crash plans."

                last_fence_seq = op.seq
                cache.accept(op)
                cache.write_back_all_flushing_stores()
                cache.write_back_all_persisted_stores()
            else:
                assert False, "invalid op type, %s, %s" % (type(op), str(op))

        return cp_list, num_reordered_records


    def gen_cp_prefixVinter_scheme(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               ignore_nt_stores : bool,
               ignore_data_stores : bool,
               ignore_copy_stores : bool,
               ignore_set_stores : bool,
               cache_nt_stores : bool, # must be **false**
               cache_data_stores : bool,
               cache_copy_stores : bool,
               cache_set_stores : bool,
               not_cache_size_threshold : int,
               not_cached_store_as_single : bool,
               overlapping_cacheline : bool, # stores in the CL that overlaps with recovery-read data
               no_real_cp : bool) -> {list, list}:
        # init the fields that will be read in recovery
        recovery_read_fields = {
            # For NOVA
            'nova_super_block': [], # empty list indicates all fields
            'journal_ptr_pair': [],
            'nova_lite_journal_entry': [],
            'nova_inode': [],
            'nova_inode_page_tail': ['next_page'],
            'nova_file_write_entry': [],
            'nova_dentry': [],
            'nova_setattr_logentry': [],
            'nova_link_change_entry': [],
            'nova_mmap_entry': [],
            # For PMFS and WineFS
            'pmfs_super_block': [],
            'pmfs_journal': [],
            'pmfs_logentry_t': [],
            'pmfs_inode_truncate_item': [],
            'pmfs_inode': ['root', 'height', 'i_blk_type', 'i_links_count', \
                           'i_mode', 'i_dtime'],
        }

        cp_list = []
        # for debugging
        num_reordered_records = []
        # 1. distinguish stores
        cached_store_list = []
        other_store_list = []
        other_store_seq_list = []
        user_data_store_seq_list = split_entry.user_space_trans_load_seq_entry_map.keys()
        user_data_store_seq_list = [x+1 for x in user_data_store_seq_list]

        for seq, entry_list in sorted(split_entry.pm_seq_entry_map.items()):
            tobe_added_other_store = None
            if entry_list[0].is_nt_store:
                if ignore_nt_stores:
                    continue
                else:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].seq in user_data_store_seq_list:
                if ignore_data_stores:
                    continue
                elif not cache_data_stores:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].type.isMemTransStore():
                if ignore_copy_stores:
                    continue
                elif not cache_copy_stores:
                    tobe_added_other_store = entry_list[0]
            if entry_list[0].type.isMemset():
                if ignore_set_stores:
                    continue
                elif not cache_set_stores:
                    tobe_added_other_store = entry_list[0]
            if not_cache_size_threshold != None and \
                    entry_list[0].type.isStoreSeries() and \
                    entry_list[0].size > not_cache_size_threshold:
                tobe_added_other_store = entry_list[0]

            if tobe_added_other_store:
                other_store_list.append(tobe_added_other_store)
                other_store_seq_list.append(tobe_added_other_store.seq)
            else:
                cached_store_list.append(entry_list[0])

        global_logger.debug(str(cached_store_list))
        global_logger.debug(str(other_store_list))

        # 2. filter out other stores that are not read in recovery
        new_other_store_list = []
        new_other_store_seq_list = []
        for store in other_store_list:
            seq = store.seq
            trace : TraceEntry = split_entry.pm_seq_entry_map[seq][0]
            if trace.stinfo_match != None:
                dbg_msg = "vinter other store st name: %s" % (trace.stinfo_match.stinfo.struct_name)
                global_logger.debug(dbg_msg)
                if trace.stinfo_match.stinfo.struct_name in recovery_read_fields:
                    dbg_msg = "vinter other store var name: %s" % (str(trace.var_list))
                    global_logger.debug(dbg_msg)
                    if len(recovery_read_fields[trace.stinfo_match.stinfo.struct_name]) == 0:
                        #  empty list indicate all fields will be read in recovery
                        dbg_msg = "vinter other store st name match: %s" % (trace.stinfo_match.stinfo.struct_name)
                        global_logger.debug(dbg_msg)
                        new_other_store_list.append(store)
                        new_other_store_seq_list.append(seq)
                    else:
                        # check if the matched variables are in the list
                        for var in trace.var_list:
                            var : StructMemberVar
                            var_name = var.var_name
                            if var_name in recovery_read_fields[trace.stinfo_match.stinfo.struct_name]:
                                dbg_msg = "vinter other store var name match: %s, %s" % (trace.stinfo_match.stinfo.struct_name, var_name)
                                global_logger.debug(dbg_msg)
                                new_other_store_list.append(store)
                                new_other_store_seq_list.append(seq)
                                break
        other_store_list = new_other_store_list
        other_store_seq_list = new_other_store_seq_list
        global_logger.debug(str(new_other_store_list))

        # 3. simulate a cache
        cache = WitcherCache(EmptyBinaryFile())
        atomic_ops = convert_entry_list_with_sampling_option(cached_store_list, sampling_nonatomic_write=False, ignore_mem_copy_set=False)
        atomic_ops.sort(key=lambda x:x.seq)

        # 4. simulating storing
        last_fence_seq = 0 if len(atomic_ops) == 0 else atomic_ops[0].seq - 1
        for op in atomic_ops:
            if isinstance(op, Store):
                cache.accept(op)
            elif isinstance(op, Flush):
                cache.accept(op)
            elif isinstance(op, Fence):
                may_read_cachelines = []
                for cacheline in cache.get_cachelines():
                    tmp = []
                    for store in cacheline.stores_list:
                        seq = store.seq
                        # 3.1 check if the store is the field that will be read in recovery
                        if seq not in split_entry.pm_seq_entry_map or \
                                len(split_entry.pm_seq_entry_map[seq]) == 0 or \
                                isinstance(split_entry.pm_seq_entry_map[seq][0], TraceEntry):
                            err_msg = "seq not in pm entry map or not a store: %d" % (seq)
                            assert False, err_msg
                        trace : TraceEntry = split_entry.pm_seq_entry_map[seq][0]
                        if trace.stinfo_match != None:
                            dbg_msg = "vinter st name: %s" % (trace.stinfo_match.stinfo.struct_name)
                            global_logger.debug(dbg_msg)
                            if trace.stinfo_match.stinfo.struct_name in recovery_read_fields:
                                dbg_msg = "vinter var name: %s" % (str(trace.var_list))
                                global_logger.debug(dbg_msg)
                                if len(recovery_read_fields[trace.stinfo_match.stinfo.struct_name]) == 0:
                                    #  empty list indicate all fields will be read in recovery
                                    tmp.append(store)
                                else:
                                    # check if the matched variables are in the list
                                    for var in trace.var_list:
                                        var : StructMemberVar
                                        var_name = var.var_name
                                        if var_name in recovery_read_fields[trace.stinfo_match.stinfo.struct_name]:
                                            dbg_msg = "vinter st and var name match: %s, %s" % (trace.stinfo_match.stinfo.struct_name, var_name)
                                            global_logger.debug(dbg_msg)
                                            tmp.append(store)
                                            break
                    if len(tmp) > 0:
                        if overlapping_cacheline == False:
                            may_read_cachelines.append([x.seq for x in tmp])
                        else:
                            may_read_cachelines.append([x.seq for x in cacheline.stores_list])

                for store in other_store_list:
                    tmp = []
                    if not (last_fence_seq < store.seq < op.seq):
                        continue
                    if not_cached_store_as_single:
                        tmp.append([store.seq, store.addr, store.size])
                    else:
                        for split_addr in range(store.addr, store.addr + store.size, ATOMIC_WRITE_BYTES):
                            split_size = store.addr + store.size - split_addr
                            split_size = split_size if split_size < ATOMIC_WRITE_BYTES else ATOMIC_WRITE_BYTES
                            tmp.append([store.seq, split_addr, split_size])
                    if len(tmp) > 0:
                        may_read_cachelines.append(tmp)

                dbg_msg = "may_read_cachelines: %s" % (str(may_read_cachelines))
                global_logger.debug(dbg_msg)

                num_reordered_records.append([])
                for cl in may_read_cachelines:
                    num_reordered_records[-1].append(cl)

                if len(may_read_cachelines) > 0:
                    total_cps = 0
                    if no_real_cp:
                        for i in range(1, len(may_read_cachelines)+1):
                            for comb_case in combinations(may_read_cachelines, i):
                                num_cps = 1
                                for seq_list in comb_case:
                                    # prefix-based reordering generates N cases,
                                    # where N is the number of elements in the list.
                                    num_cps *= len(seq_list)
                                total_cps += num_cps
                        cp = CrashPlanEntry(CrashPlanType.Vinter, -1, 0, {}, {}, 'no_pickle')
                        cp.num_cp_entries = total_cps
                        cp_list.append(cp)
                        dbg_msg = "Vinter scheme number cps: %d" % (cp.num_cp_entries)
                        global_logger.debug(dbg_msg)
                    else:
                        visited_cp = set()
                        for i in range(1, len(may_read_cachelines)+1):
                            for comb_case in combinations(may_read_cachelines, i):
                                max_stores_in_cacheline = max([len(x) for x in comb_case])
                                for j in range(max_stores_in_cacheline):
                                    # select j-prefix
                                    for k in range(1, len(comb_case) + 1):
                                        # select k cachelines to persist j-prefix
                                        for selected_cachelines in combinations(comb_case, k):
                                            tobe_persisted = []
                                            tobe_hashed = []
                                            for selected_cl in selected_cachelines:
                                                for element in selected_cl[:j]:
                                                    if isinstance(element, list):
                                                        if not_cached_store_as_single:
                                                            tobe_hashed.append(element[0])
                                                        else:
                                                            tobe_hashed.append(element[0] + element[1])
                                                        # TODO: if store is splitted to cacheline size,
                                                        # we need to persist the partial of the stored data rather the
                                                        # whole stored data
                                                        tobe_persisted.append(element[0])
                                                    elif isinstance(element, int):
                                                        tobe_persisted.append(element)
                                                        tobe_hashed.append(element)
                                                    else:
                                                        dbg_msg = "do not know the type of the element in the cache line: %s" % (str(selected_cl))
                                                        global_logger.debug(dbg_msg)
                                            try:
                                                if frozenset(tobe_hashed) not in visited_cp:
                                                    visited_cp.add(frozenset(tobe_hashed))
                                                    cp = CrashPlanEntry(CrashPlanType.Vinter, \
                                                                        -1, last_fence_seq,
                                                                        set(tobe_persisted), set(tobe_persisted),
                                                                        "Vinter")
                                                    cp_list.append(cp)
                                            except TypeError as e:
                                                dbg_msg = "An error occurred:" + str(e)
                                                dbg_msg += "\n%s" % (str(tobe_persisted))
                                                global_logger.debug(dbg_msg)
                                                assert False, dbg_msg
                        dbg_msg = "Vinter scheme number cps: %d" % (len(cp_list))
                        global_logger.debug(dbg_msg)

                last_fence_seq = op.seq
                cache.accept(op)
                cache.write_back_all_flushing_stores()
                cache.write_back_all_persisted_stores()
            else:
                assert False, "invalid op type, %s, %s" % (type(op), str(op))

        return cp_list, num_reordered_records

    """
    Vinter:
    1. Traces both temporal stores and non-temporal stores
    2. Reorders cache lines
    3. Prefix-based in-cache-line reordering
    4. Samples if the number of crash plans exceeds a threshold
    5. Has two schemes:
        a. reorder the write that will be read in recovery
        b. reorder all writes that in the cache line that will be read in recovery
    Implementation:
    1. Since we do not have the information of which write will be read in recovery,
       and the implementation will break our current framework,
       currently we do not distingush writes that will be read in recovery
       and reorder cache lines and all writes inside it.
       We manually determine the writes that will be read in recovery.
       For NOVA:
            snapshot related: since we/vinter/chipmunk does not test snapshot, we ignore it here.
            nova_super_block: the whole SB will be read in recovery, since nova checks the checksum in recovery.
            journal_ptr_pair: whole data structure will be read
            nova_lite_journal_entry: whole data structure will be read
            nova_inode: whole data structure will be read due to the checksum and rebuild of the inode allocator
            nova_inode_page_tail:
                next_page: will be read to rebuild the page allocator
            nova_file_write_entry: whole data structure will be read due to checksum checks
            nova_dentry: whole data structure will be read due to checksum checks
            nova_setattr_logentry: whole data structure will be read due to checksum checks
            nova_link_change_entry: whole data structure will be read due to checksum checks
            nova_mmap_entry: since we/vinter/chipmunk does not test snapshot, we ignore it here.
            nova_snapshot_info_entry: since we/vinter/chipmunk does not test snapshot, we ignore it here.
       For PMFS and WineFS:
            pmfs_super_block: it has the checksum
            pmfs_journal: all
            pmfs_logentry_t: all
            pmfs_inode_truncate_item: all
            pmfs_inode:
                root: the root ptr to the extent tree
                height: the height of the extent tree
                i_blk_type: the allocated block type of this inode
                i_links_count: link counts
                i_mode: file mode
                i_dtime: deletion time
                Since the extent tree is not represented by a data structure, we do not know them,
                and cannot determine whether they are read/written in recovery/operations.
    2. reorder_read_cacheline: if it is false, only reorder the writes that will be
       read in recovery. Otherwise, reorder all writes in the cache line that will
       be read in recovery.
    3. no_real_cp: always true due to the large number of crash plans.
    """
    def gen_cp_vinter_scheme(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               reorder_read_cacheline : bool,
               no_real_cp : bool) -> {list, list}:
        # init the fields that will be read in recovery
        recovery_read_fields = {
            # For NOVA
            'nova_super_block': [], # empty list indicates all fields
            'journal_ptr_pair': [],
            'nova_lite_journal_entry': [],
            'nova_inode': [],
            'nova_inode_page_tail': ['next_page'],
            'nova_file_write_entry': [],
            'nova_dentry': [],
            'nova_setattr_logentry': [],
            'nova_link_change_entry': [],
            'nova_mmap_entry': [],
            # For PMFS and WineFS
            'pmfs_super_block': [],
            'pmfs_journal': [],
            'pmfs_logentry_t': [],
            'pmfs_inode_truncate_item': [],
            'pmfs_inode': ['root', 'height', 'i_blk_type', 'i_links_count', \
                           'i_mode', 'i_dtime'],
        }

        cp_list = []
        # for debugging
        num_reordered_records = []

        # 1. convert writes to atomic stores
        atomic_ops = convert_seq_entrylist_dict(split_entry.pm_seq_entry_map,
                                                False, False, False, False, False, dict())
        atomic_ops.sort(key=lambda x:x.seq)

        # 2. simulate a cache
        cache = WitcherCache(EmptyBinaryFile())

        # 3. simulating stores
        last_fence_seq = 0 if len(atomic_ops) == 0 else atomic_ops[0].seq - 1
        for op in atomic_ops:
            if isinstance(op, Store):
                cache.accept(op)
            elif isinstance(op, Flush):
                cache.accept(op)
            elif isinstance(op, Fence):
                may_read_cachelines = []
                for cacheline in cache.get_cachelines():
                    tmp = []
                    for store in cacheline.stores_list:
                        seq = store.seq
                        # 3.1 check if the store is the field that will be read in recovery
                        if seq not in split_entry.pm_seq_entry_map or \
                                len(split_entry.pm_seq_entry_map[seq]) == 0 or \
                                isinstance(split_entry.pm_seq_entry_map[seq][0], TraceEntry):
                            err_msg = "seq not in pm entry map or not a store: %d" % (seq)
                            assert False, err_msg
                        trace : TraceEntry = split_entry.pm_seq_entry_map[seq][0]
                        if trace.stinfo_match != None:
                            dbg_msg = "vinter st name: %s" % (trace.stinfo_match.stinfo.struct_name)
                            global_logger.debug(dbg_msg)
                            if trace.stinfo_match.stinfo.struct_name in recovery_read_fields:
                                dbg_msg = "vinter var name: %s" % (str(trace.var_list))
                                global_logger.debug(dbg_msg)
                                if len(recovery_read_fields[trace.stinfo_match.stinfo.struct_name]) == 0:
                                    #  empty list indicate all fields will be read in recovery
                                    tmp.append(store)
                                else:
                                    # check if the matched variables are in the list
                                    for var in trace.var_list:
                                        var : StructMemberVar
                                        var_name = var.var_name
                                        if var_name in recovery_read_fields[trace.stinfo_match.stinfo.struct_name]:
                                            dbg_msg = "vinter st and var name match: %s, %s" % (trace.stinfo_match.stinfo.struct_name, var_name)
                                            global_logger.debug(dbg_msg)
                                            tmp.append(store)
                                            break
                    if len(tmp) > 0:
                        if reorder_read_cacheline == False:
                            may_read_cachelines.append([x.seq for x in tmp])
                        else:
                            may_read_cachelines.append([x.seq for x in cacheline.stores_list])
                dbg_msg = "may_read_cachelines: %s" % (str(may_read_cachelines))
                global_logger.debug(dbg_msg)

                num_reordered_records.append([])
                for cl in may_read_cachelines:
                    num_reordered_records[-1].append(cl)

                if len(may_read_cachelines) > 0:
                    total_cps = 0
                    if no_real_cp:
                        for i in range(1, len(may_read_cachelines)+1):
                            for comb_case in combinations(may_read_cachelines, i):
                                num_cps = 1
                                for seq_list in comb_case:
                                    # prefix-based reordering generates N cases,
                                    # where N is the number of elements in the list.
                                    num_cps *= len(seq_list)
                                total_cps += num_cps
                        cp = CrashPlanEntry(CrashPlanType.Vinter, -1, 0, {}, {}, 'no_pickle')
                        cp.num_cp_entries = total_cps
                        cp_list.append(cp)
                        dbg_msg = "Vinter scheme number cps: %d" % (cp.num_cp_entries)
                        global_logger.debug(dbg_msg)
                    else:
                        visited_cp = set()
                        for i in range(1, len(may_read_cachelines)+1):
                            for comb_case in combinations(may_read_cachelines, i):
                                max_stores_in_cacheline = max([len(x) for x in comb_case])
                                for j in range(max_stores_in_cacheline):
                                    # select j-prefix
                                    for k in range(1, len(comb_case) + 1):
                                        # select k cachelines to persist j-prefix
                                        for selected_cachelines in combinations(comb_case, k):
                                            tobe_persisted = []
                                            for selected_cl in selected_cachelines:
                                                tobe_persisted += selected_cl[:j]
                                            if len(tobe_persisted) == 0:
                                                dbg_msg = "tobe_persisted is empty. may_read_cachelines: %s, comb_case: %s, selected_cachelines: %s" % (str(may_read_cachelines), str(comb_case), str(selected_cachelines))
                                                global_logger.debug(dbg_msg)
                                                continue
                                            if frozenset(tobe_persisted) not in visited_cp:
                                                visited_cp.add(frozenset(tobe_persisted))
                                                cp = CrashPlanEntry(CrashPlanType.Vinter, \
                                                                    -1, last_fence_seq,
                                                                    set(tobe_persisted), set(tobe_persisted),
                                                                    "Vinter")
                                                cp_list.append(cp)
                        dbg_msg = "Vinter scheme number cps: %d" % (len(cp_list))
                        global_logger.debug(dbg_msg)

                last_fence_seq = op.seq
                cache.accept(op)
                cache.write_back_all_flushing_stores()
                cache.write_back_all_persisted_stores()
            else:
                assert False, "invalid op type, %s, %s" % (type(op), str(op))

        return cp_list, num_reordered_records


    def gen_cp_schemes(self,
               split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               lsw_reason : MechLSWReason,
               rep_reason : MechReplReason,
               undojnl_reason : MechUndoJnlReason) -> None:
        global glo_consider_cl_prefix_in_2cp
        # 0. for writing result to a file
        self.dump_data = ""

        # 1. generate 2cp
        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_2cp(split_entry, pmstore_reason,
        #                           sampling_nonatomic_write = False,
        #                           ignore_mem_copy_set = False,
        #                           nonatmic_as_single_write = False,
        #                           consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_2cp without sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_2cp(split_entry, pmstore_reason,
                                  sampling_nonatomic_write = True,
                                  ignore_mem_copy_set = False,
                                  nonatmic_as_single_write = False,
                                  consider_cl_prefix = False)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_2cp with sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_2cp(split_entry, pmstore_reason,
                                  sampling_nonatomic_write = False,
                                  ignore_mem_copy_set = False,
                                  nonatmic_as_single_write = True,
                                  consider_cl_prefix = False)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_2cp nonatomic as single: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_2cp(split_entry, pmstore_reason,
                                  sampling_nonatomic_write = True,
                                  ignore_mem_copy_set = False,
                                  nonatmic_as_single_write = False,
                                  consider_cl_prefix = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_2cp prefix-reordering with sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_2cp(split_entry, pmstore_reason,
                                  sampling_nonatomic_write = False,
                                  ignore_mem_copy_set = False,
                                  nonatmic_as_single_write = True,
                                  consider_cl_prefix = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_2cp prefix-reordering nonatomic as single: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)


        # 2. mech with 2cp
        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_mech_2cp(split_entry, pmstore_reason, \
        #                                lsw_reason, rep_reason, undojnl_reason, \
        #                                sampling_nonatomic_write = False, \
        #                                ignore_mem_copy_set = False, \
        #                                nonatmic_as_single_write = False,
        #                                consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_mech_2cp without sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_mech_2cp(split_entry, pmstore_reason, \
                                       lsw_reason, rep_reason, undojnl_reason, \
                                       sampling_nonatomic_write = True, \
                                       ignore_mem_copy_set = False, \
                                       nonatmic_as_single_write = False,
                                       consider_cl_prefix = False)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_mech_2cp with sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_mech_2cp(split_entry, pmstore_reason, \
                                       lsw_reason, rep_reason, undojnl_reason, \
                                       sampling_nonatomic_write = False, \
                                       ignore_mem_copy_set = False, \
                                       nonatmic_as_single_write = True,
                                       consider_cl_prefix = False)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_mech_2cp nonatomic as single: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_mech_2cp(split_entry, pmstore_reason, \
                                       lsw_reason, rep_reason, undojnl_reason, \
                                       sampling_nonatomic_write = True, \
                                       ignore_mem_copy_set = False, \
                                       nonatmic_as_single_write = False,
                                       consider_cl_prefix = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_mech_2cp prefix-reordering with sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_mech_2cp(split_entry, pmstore_reason, \
                                       lsw_reason, rep_reason, undojnl_reason, \
                                       sampling_nonatomic_write = False, \
                                       ignore_mem_copy_set = False, \
                                       nonatmic_as_single_write = True,
                                       consider_cl_prefix = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_mech_2cp prefix-reordering nonatomic as single: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)


        # 3. mech with comb
        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_mech_comb(split_entry, pmstore_reason,
        #                                 lsw_reason, rep_reason, undojnl_reason,
        #                                 sampling_nonatomic_write = False,
        #                                 ignore_mem_copy_set = False,
        #                                 nonatmic_as_single_write = False)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_mech_comb without sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_mech_comb(split_entry, pmstore_reason,
                                        lsw_reason, rep_reason, undojnl_reason,
                                        sampling_nonatomic_write = True,
                                        ignore_mem_copy_set = False,
                                        nonatmic_as_single_write = False)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_mech_comb with sampling: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_mech_comb(split_entry, pmstore_reason,
                                        lsw_reason, rep_reason, undojnl_reason,
                                        sampling_nonatomic_write = False,
                                        ignore_mem_copy_set = False,
                                        nonatmic_as_single_write = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_mech_comb nonatomic as single: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)


        # 4. generate crash plans based on cache-line-based reordering scheme
        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_cachelinereordering_scheme(split_entry, pmstore_reason,
        #         ignore_nt_stores = False, ignore_data_stores = False,
        #         ignore_copy_stores = False, ignore_set_stores = False,
        #         cache_nt_stores = False, cache_data_stores = True,
        #         cache_copy_stores = True, cache_set_stores = True,
        #         not_cache_size_threshold = None,
        #         not_cached_store_coalesce = False, no_real_cp = True)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_cachelinereordering_scheme nt_stores: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)

        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_cachelinereordering_scheme(split_entry, pmstore_reason,
        #         ignore_nt_stores = False, ignore_data_stores = False,
        #         ignore_copy_stores = False, ignore_set_stores = False,
        #         cache_nt_stores = False, cache_data_stores = False,
        #         cache_copy_stores = True, cache_set_stores = True,
        #         not_cache_size_threshold = None,
        #         not_cached_store_coalesce = False, no_real_cp = True)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_cachelinereordering_scheme nt_store data_store: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_cachelinereordering_scheme(split_entry, pmstore_reason,
                ignore_nt_stores = False, ignore_data_stores = False,
                ignore_copy_stores = False, ignore_set_stores = False,
                cache_nt_stores = False, cache_data_stores = False,
                cache_copy_stores = False, cache_set_stores = False,
                not_cache_size_threshold = 20, # consider 20 bytes writes as a single store
                not_cached_store_coalesce = False, no_real_cp = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_cachelinereordering_scheme nonatomic stores: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_cachelinereordering_scheme(split_entry, pmstore_reason,
        #         ignore_nt_stores = False, ignore_data_stores = False,
        #         ignore_copy_stores = False, ignore_set_stores = False,
        #         cache_nt_stores = False, cache_data_stores = False,
        #         cache_copy_stores = False, cache_set_stores = False,
        #         not_cache_size_threshold = 20, # consider 20 bytes writes as a single store
        #         not_cached_store_coalesce = True, no_real_cp = True)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_cachelinereordering_scheme nonatomic stores coalesce: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)


        # 5. generate crash plans based on the prefix-based reordering scheme
        # This full scheme is too time-consuming, triggering the timeout issue.
        # cp_list = self.gen_cp_prefixreordering_scheme(split_entry, pmstore_reason,
        #         ignore_nt_stores = False, ignore_data_stores = False,
        #         ignore_copy_stores = False, ignore_set_stores = False,
        #         cache_nt_stores = False, cache_data_stores = True,
        #         cache_copy_stores = True, cache_set_stores = True,
        #         not_cache_size_threshold = None,
        #         not_cached_store_as_single = False, no_real_cp = True)
        # dbg_msg = "gen_cp_prefixreordering_scheme full:\n%s" % (self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_prefixreordering_scheme(split_entry, pmstore_reason,
                ignore_nt_stores = False, ignore_data_stores = False,
                ignore_copy_stores = False, ignore_set_stores = False,
                cache_nt_stores = False, cache_data_stores = False,
                cache_copy_stores = False, cache_set_stores = False,
                not_cache_size_threshold = 20, # consider 20 bytes writes as a single store
                not_cached_store_as_single = True, no_real_cp = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_prefixreordering_scheme nonatomic stores: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)


        # 6. generate crash plans based on Chipmunk
        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_cachelineChipmunk_scheme(split_entry, pmstore_reason,
                not_cache_size_threshold = 5 * CACHELINE_BYTES, # Chipmunk considers 5 * cacheline-size bytes writes as a single store
                no_real_cp = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_cachelineChipmunk_scheme chipmunk: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)


        # 7. generate crash plans based on Vinter
        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_vinter_scheme( \
        #             split_entry, pmstore_reason,
        #             reorder_read_cacheline = False,
        #             no_real_cp = True)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_vinter_scheme overlapping_store: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)

        # start_time = datetime.datetime.now()
        # cp_list, num_reordered_records = self.gen_cp_vinter_scheme( \
        #             split_entry, pmstore_reason,
        #             reorder_read_cacheline = True,
        #             no_real_cp = True)
        # elapsed_time = datetime.datetime.now() - start_time
        # elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        # dbg_msg = "gen_cp_vinter_scheme overlapping_cacheline: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        # self.dump_data += dbg_msg
        # self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        # global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_prefixVinter_scheme( \
                    split_entry, pmstore_reason,
                    ignore_nt_stores = False, ignore_data_stores = False,
                    ignore_copy_stores = False, ignore_set_stores = False,
                    cache_nt_stores = False, cache_data_stores = False,
                    cache_copy_stores = False, cache_set_stores = False,
                    not_cache_size_threshold = 20,
                    not_cached_store_as_single = True,
                    overlapping_cacheline = False,
                    no_real_cp = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_prefixVinter_scheme overlapping_store: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)

        start_time = datetime.datetime.now()
        cp_list, num_reordered_records = self.gen_cp_prefixVinter_scheme( \
                    split_entry, pmstore_reason,
                    ignore_nt_stores = False, ignore_data_stores = False,
                    ignore_copy_stores = False, ignore_set_stores = False,
                    cache_nt_stores = False, cache_data_stores = False,
                    cache_copy_stores = False, cache_set_stores = False,
                    not_cache_size_threshold = 20,
                    not_cached_store_as_single = True,
                    overlapping_cacheline = True,
                    no_real_cp = True)
        elapsed_time = datetime.datetime.now() - start_time
        elapsed_time = str(elapsed_time.seconds * 1000000 + elapsed_time.microseconds)
        dbg_msg = "gen_cp_prefixVinter_scheme overlapping_cacheline: %s\n%s" % (elapsed_time, self.dbg_get_cp_list_count(cp_list))
        self.dump_data += dbg_msg
        self.dump_data += "## num_reordered_records: %s\n" % (str(num_reordered_records))
        global_logger.debug(dbg_msg)


        # 8. generate the real crash plans with pickles
        global glo_use_mech_2cp_with_sampling, \
               glo_use_mech_2cp_without_sampling, \
               glo_use_2cp_with_sampling, \
               glo_use_2cp_without_sampling, \
               glo_use_mech_comb_with_sampling, \
               glo_use_mech_comb_without_sampling, \
               glo_use_cachelinereordering_scheme, \
               glo_cachelinereordering_no_cp_pickle, \
               glo_use_vinter_scheme, \
               glo_use_vinter_no_cp_pickle, \
               glo_use_vinter_overlap_cacheline, \
               glo_use_chipmunk_scheme, \
               glo_use_chipmunk_no_cp_pickle
        ignore_mem_copy_set = False
        self.gen_cp_for_oracle(pmstore_reason, split_entry)
        if glo_use_mech_2cp_with_sampling:
            self.entry_list, _ = self.gen_cp_mech_2cp(split_entry, pmstore_reason,
                                                   lsw_reason, rep_reason, undojnl_reason,
                                                   sampling_nonatomic_write = True,
                                                   ignore_mem_copy_set = False,
                                                   nonatmic_as_single_write = False,
                                                   consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        elif glo_use_mech_2cp_without_sampling:
            self.entry_list, _ = self.gen_cp_mech_2cp(split_entry, pmstore_reason,
                                                   lsw_reason, rep_reason, undojnl_reason,
                                                   sampling_nonatomic_write = False,
                                                   ignore_mem_copy_set = False,
                                                   nonatmic_as_single_write = False,
                                                   consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        elif glo_use_mech_2cp_nonatomic_as_single:
            self.entry_list, _ = self.gen_cp_mech_2cp(split_entry, pmstore_reason,
                                                   lsw_reason, rep_reason, undojnl_reason,
                                                   sampling_nonatomic_write = False,
                                                   ignore_mem_copy_set = False,
                                                   nonatmic_as_single_write = True,
                                                   consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        elif glo_use_2cp_with_sampling:
            self.entry_list, _ = self.gen_cp_2cp(split_entry, pmstore_reason,
                            sampling_nonatomic_write = True,
                            ignore_mem_copy_set = False,
                            nonatmic_as_single_write = False,
                            consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        elif glo_use_2cp_without_sampling:
            self.entry_list, _ = self.gen_cp_2cp(split_entry, pmstore_reason,
                            sampling_nonatomic_write = False,
                            ignore_mem_copy_set = False,
                            nonatmic_as_single_write = False,
                            consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        elif glo_use_2cp_nonatomic_as_single:
            self.entry_list, _ = self.gen_cp_2cp(split_entry, pmstore_reason,
                            sampling_nonatomic_write = False,
                            ignore_mem_copy_set = False,
                            nonatmic_as_single_write = True,
                            consider_cl_prefix = glo_consider_cl_prefix_in_2cp)
        elif glo_use_mech_comb_with_sampling:
            warn_msg = "mech+comb does not produce pickles due to the huge number of crash plans"
            global_logger.warning(warn_msg)
            self.entry_list, _ = self.gen_cp_mech_comb(split_entry, pmstore_reason,
                                                    lsw_reason, rep_reason, undojnl_reason,
                                                    sampling_nonatomic_write = True,
                                                    ignore_mem_copy_set = False,
                                                    nonatmic_as_single_write = False)
        elif glo_use_mech_comb_without_sampling:
            warn_msg = "mech+comb does not produce pickles due to the huge number of crash plans"
            global_logger.warning(warn_msg)
            self.entry_list, _ = self.gen_cp_mech_comb(split_entry, pmstore_reason,
                                                    lsw_reason, rep_reason, undojnl_reason,
                                                    sampling_nonatomic_write = False,
                                                    ignore_mem_copy_set = False,
                                                    nonatmic_as_single_write = False)
        elif glo_use_mech_comb_nonatomic_as_single:
            warn_msg = "mech+comb does not produce pickles due to the huge number of crash plans"
            global_logger.warning(warn_msg)
            self.entry_list, _ = self.gen_cp_mech_comb(split_entry, pmstore_reason,
                                                    lsw_reason, rep_reason, undojnl_reason,
                                                    sampling_nonatomic_write = False,
                                                    ignore_mem_copy_set = False,
                                                    nonatmic_as_single_write = True)
        elif glo_use_cachelinereordering_scheme:
            self.entry_list, num_reordered_records = self.gen_cp_cachelinereordering_scheme( \
                    split_entry, pmstore_reason,
                    ignore_nt_stores = False, ignore_data_stores = False,
                    ignore_copy_stores = False, ignore_set_stores = False,
                    cache_nt_stores = False, cache_data_stores = False,
                    cache_copy_stores = False, cache_set_stores = False,
                    not_cache_size_threshold = 20,
                    not_cached_store_coalesce = False,
                    no_real_cp = glo_cachelinereordering_no_cp_pickle)
        elif glo_use_vinter_scheme:
            self.entry_list, num_reordered_records = self.gen_cp_prefixVinter_scheme( \
                    split_entry, pmstore_reason,
                    ignore_nt_stores = False, ignore_data_stores = False,
                    ignore_copy_stores = False, ignore_set_stores = False,
                    cache_nt_stores = False, cache_data_stores = False,
                    cache_copy_stores = False, cache_set_stores = False,
                    not_cache_size_threshold = 20,
                    not_cached_store_as_single = True,
                    overlapping_cacheline = glo_use_vinter_overlap_cacheline,
                    no_real_cp = glo_use_vinter_no_cp_pickle)
        elif glo_use_chipmunk_scheme:
            self.entry_list, num_reordered_records = self.gen_cp_cachelineChipmunk_scheme(split_entry, pmstore_reason,
                not_cache_size_threshold = 5 * CACHELINE_BYTES, # Chipmunk considers 5 * cacheline-size bytes writes as a single store
                no_real_cp = glo_use_chipmunk_no_cp_pickle)

        else:
            warn_msg = "not select a scheme for generating crash plans"
            global_logger.warning(warn_msg)


    def dbg_get_cp_list_count(self, cp_list : list):
        num_mech_cps = 0
        num_unps_cps = 0
        for cp in cp_list:
            if cp.type == CrashPlanType.Unguarded or \
                    cp.type == CrashPlanType.UnguardedPSelf or \
                    cp.type == CrashPlanType.UnguardedPOther or \
                    cp.type == CrashPlanType.CacheLineReordering or \
                    cp.type == CrashPlanType.PrefixReordering or \
                    cp.type == CrashPlanType.Chipmunk or \
                    cp.type == CrashPlanType.Vinter:
                num_unps_cps += cp.num_cp_entries
            else:
                num_mech_cps += cp.num_cp_entries
        buf = ''
        buf += "orcl: %d\n" % (2)
        buf += "mech: %d\n" % (num_mech_cps)
        buf += "unps: %d\n" % (num_unps_cps)
        return buf


    def dbg_get_detail(self):
        data = ""
        num = 0
        for entry in self.entry_list:
            num += 1
            data += "Crash Plan #%d\n" % (num)
            data += str(entry).strip() + "\n\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
