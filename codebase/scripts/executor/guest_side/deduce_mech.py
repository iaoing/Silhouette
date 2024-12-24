import os
import sys
import time
from enum import Enum
import traceback
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde
from pymemcache import MemcacheUnexpectedCloseError

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase
from scripts.fs_conf.base.module_default import ModuleDefault
from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.trace_proc.trace_reader.trace_reader import TraceReader, TraceEntry
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr, OpTraceEntry
from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.utils.utils import getTimestamp, fileExists
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
import scripts.vm_comm.memcached_lock as mc_lock
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.cheat_sheet.base.cheat_base import CheatSheetBase, UndoJnlCheatSheetBase, LSWCheatSheetBase, RepCheatSheetBase
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason
from scripts.mech_reason.mech_memcpy.mech_memcpy_reason import MechMemcpyReason
from scripts.mech_reason.mech_memset.mech_memset_reason import MechMemsetReason
from scripts.mech_reason.mech_link.mech_link_reason import MechLinkReason
from scripts.mech_reason.mech_undojnl.mech_undojnl_reason import MechUndoJnlReason, MechUndoJnlEntry, UndoJnlLoggingEntry
from scripts.mech_reason.mech_replication.mech_repl_reason import MechReplReason, MechReplEntry
from scripts.mech_reason.mech_lsw.mech_lsw_reason import MechLSWReason, MechLSWEntry
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.deduce_mech.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class InvariantCheckErrorTypes(Enum):
    GOOD              = 'good'
    UNDO_JNL_ERROR    = 'undo_jnl_error'
    REPLICATION_ERROR = 'replication_error'
    LSW_ERROR         = 'lsw_error'

def _get_unique_count_by_incr(memcached_client, key):
    num = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return num

def proc_invariant_check_rst(memcached_client, tp: InvariantCheckErrorTypes, basename : str, op_name_list : list, err_list : list, other_msg : str):
    existing_key = f'InvariantCheckErrorTypes.{tp.value}.{op_name_list[-1]}.{str(set(err_list))}'
    existing_key = str(hash(existing_key))
    if mc_wrapper.mc_add_wrapper(memcached_client, existing_key, '1', noreply=False) == True:
        report_time = getTimestamp()
        # no err list inserted before for this error type 'tp' and this operation 'op_name_list[-1]'
        key = f'InvariantCheckErrorTypes.{tp.value}.count'
        num = _get_unique_count_by_incr(memcached_client, key)

        key = f'InvariantCheckErrorTypes.{tp.value}.{num}'
        value = [report_time, basename, op_name_list, err_list, other_msg]
        mc_wrapper.mc_set_wrapper(memcached_client, key, value)
    else:
        # such information has been inserted, do not insert it again
        pass

class DeduceMech:
    def __init__(self, cheatsheet : CheatSheetBase, memcached_client):
        self.cheatsheet = cheatsheet
        self.memcached_client = memcached_client

        # some cheat sheet information need to track
        self.undo_jnl_cheatsheet : UndoJnlCheatSheetBase = self.cheatsheet.undo_jnl_sheet
        self.rep_cheatsheet : RepCheatSheetBase = self.cheatsheet.rep_sheet
        # a list of LSWCheatSheetBase
        self.lsw_cheatsheet_list : list = self.cheatsheet.lsw_sheet_list

        self.clean()

    def clean(self):
        self.basename = None
        self.op_name_list = None

        self.pmstore_reason : MechPMStoreReason= None
        self.memcpy_reason : MechMemcpyReason = None
        self.memset_reason : MechMemsetReason = None
        self.link_reason : MechLinkReason = None
        self.undojnl_reason : MechUndoJnlReason = None
        self.rep_reason : MechReplReason = None
        # a list of MechLSWReason
        self.lsw_reason_list : list = []

    def set_info(self, basename : str, op_name_list : list):
        self.basename = basename
        self.op_name_list = op_name_list

    @timeit
    def update_necessary_computations(self, trace_reader : TraceReader, op_entry : OpTraceEntry, start_seq : int, end_seq : int, is_mount_op : bool):
        if log.debug:
            msg = f"before update_necessary_computations:\n{self.undo_jnl_cheatsheet.buf_addr_computation}\n{self.undo_jnl_cheatsheet.buf_size_computation}\n{self.undo_jnl_cheatsheet.head_computation}\n{self.undo_jnl_cheatsheet.tail_computation}"
            log.global_logger.debug(msg)

        if op_entry != None:
            for seq, entry_list in op_entry.pm_seq_entry_map.items():
                trace_entry : TraceEntry = entry_list[0]
                if self.undo_jnl_cheatsheet:
                    if is_mount_op:
                        self.undo_jnl_cheatsheet.update_circular_buf_addr(trace_entry)
                        self.undo_jnl_cheatsheet.update_circular_buf_size(trace_entry)
                    self.undo_jnl_cheatsheet.update_head(trace_entry)
                    self.undo_jnl_cheatsheet.update_tail(trace_entry)

                for lsw_cheatsheet in self.lsw_cheatsheet_list:
                    lsw_cheatsheet : LSWCheatSheetBase
                    lsw_cheatsheet.update_tail(trace_entry)
                    lsw_cheatsheet.update_log_space_size(trace_entry)

        else:
            for seq in trace_reader.pm_store_seq_list:
                if seq < start_seq:
                    continue
                elif seq > end_seq:
                    break
                else:
                    trace_entry : TraceEntry = trace_reader.seq_entry_map[seq][0]
                    if self.undo_jnl_cheatsheet:
                        if is_mount_op:
                            self.undo_jnl_cheatsheet.update_circular_buf_addr(trace_entry)
                            self.undo_jnl_cheatsheet.update_circular_buf_size(trace_entry)
                        self.undo_jnl_cheatsheet.update_head(trace_entry)
                        self.undo_jnl_cheatsheet.update_tail(trace_entry)

                for lsw_cheatsheet in self.lsw_cheatsheet_list:
                    lsw_cheatsheet : LSWCheatSheetBase
                    lsw_cheatsheet.update_tail(trace_entry)
                    lsw_cheatsheet.update_log_space_size(trace_entry)

        if log.debug:
            msg = f"after update_necessary_computations:\n{self.undo_jnl_cheatsheet.buf_addr_computation}\n{self.undo_jnl_cheatsheet.buf_size_computation}\n{self.undo_jnl_cheatsheet.head_computation}\n{self.undo_jnl_cheatsheet.tail_computation}"
            log.global_logger.debug(msg)

    @timeit
    def deduce_pmstore(self, op_entry : OpTraceEntry):
        if not self.pmstore_reason:
            self.pmstore_reason : MechPMStoreReason = MechPMStoreReason(op_entry)
            if log.debug:
                msg = f"pmstore reason detail:\n{self.pmstore_reason.dbg_get_detail()}"
                log.global_logger.debug(msg)

    @timeit
    def deduce_memcpy(self, op_entry : OpTraceEntry):
        if not self.memcpy_reason:
            self.memcpy_reason : MechMemcpyReason = MechMemcpyReason(op_entry)
            if log.debug:
                msg = f"memcpy reason detail:\n{self.memcpy_reason.dbg_get_detail()}"
                log.global_logger.debug(msg)

    @timeit
    def deduce_memset(self, op_entry : OpTraceEntry):
        if not self.memset_reason:
            self.deduce_pmstore(op_entry)
            self.memset_reason : MechMemsetReason = MechMemsetReason(op_entry, self.pmstore_reason)
            if log.debug:
                msg = f"memset reason detail:\n{self.memset_reason.dbg_get_detail()}"
                log.global_logger.debug(msg)

    @timeit
    def deduce_link(self, op_entry : OpTraceEntry, st_index : StInfoIndex):
        if not self.link_reason:
            self.deduce_pmstore(op_entry)
            self.link_reason = MechLinkReason(op_entry, self.pmstore_reason, st_index)
            if log.debug:
                msg = f"link reason detail:\n{self.link_reason.dbg_get_detail()}"
                log.global_logger.debug(msg)

    @timeit
    def deduce_undojnl(self, op_entry : OpTraceEntry):
        if not self.undojnl_reason and self.undo_jnl_cheatsheet:
            self.undojnl_reason = MechUndoJnlReason(op_entry, self.pmstore_reason, self.undo_jnl_cheatsheet)
            if log.debug:
                msg = f"undo_jnl reason detail:\n{self.undojnl_reason.dbg_get_detail()}"
                log.global_logger.debug(msg)

            err_list = self.undojnl_reason.invariant_check()
            if len(err_list) > 0:
                msg = f"{err_list}\n{self.undojnl_reason.dbg_get_detail()}"
                log.global_logger.error(msg)
                proc_invariant_check_rst(self.memcached_client, InvariantCheckErrorTypes.UNDO_JNL_ERROR, self.basename, self.op_name_list, err_list, msg)

    @timeit
    def deduce_replication(self, op_entry : OpTraceEntry):
        if not self.rep_reason and self.rep_cheatsheet:
            self.deduce_pmstore(op_entry)
            self.deduce_memcpy(op_entry)
            self.rep_reason = MechReplReason(op_entry, self.pmstore_reason, self.memcpy_reason, self.cheatsheet.rep_sheet)

            if log.debug:
                msg = self.rep_reason.dbg_get_detail()
                log.global_logger.debug(msg)

            err_list = self.rep_reason.invariant_check()
            if len(err_list) > 0:
                msg = f"{err_list}\n{self.rep_reason.dbg_get_detail()}"
                log.global_logger.error(msg)
                proc_invariant_check_rst(self.memcached_client, InvariantCheckErrorTypes.REPLICATION_ERROR, self.basename, self.op_name_list, err_list, msg)

    @timeit
    def deduce_lsw(self, op_entry : OpTraceEntry, st_index : StInfoIndex):
        if len(self.lsw_reason_list) == 0 and len(self.lsw_cheatsheet_list) > 0:
            self.deduce_pmstore(op_entry)
            self.deduce_link(op_entry, st_index)
            self.deduce_undojnl(op_entry)
            self.deduce_replication(op_entry)

            for lsw_sheet in self.lsw_cheatsheet_list:
                lsw_sheet : LSWCheatSheetBase
                lsw_reason = MechLSWReason(op_entry, self.pmstore_reason, self.link_reason, self.undojnl_reason, self.rep_reason, lsw_sheet)
                self.lsw_reason_list.append(lsw_reason)

            err_list = []
            for lsw_reason in self.lsw_reason_list:
                lsw_reason : MechLSWReason

                if log.debug:
                    msg = lsw_reason.dbg_get_detail()
                    log.global_logger.debug(msg)

                err_list = lsw_reason.invariant_check()

                if len(err_list) > 0:
                    msg = f"{err_list}\n{lsw_reason.dbg_get_detail()}"
                    log.global_logger.error("LSW invariant check failed:\n" + msg)
                    proc_invariant_check_rst(self.memcached_client, InvariantCheckErrorTypes.LSW_ERROR, self.basename, self.op_name_list, err_list, msg)

    def get_persist_seq(self, check_unsafe : bool, check_recovery : bool):
        '''
        Returns persist_self_seq_set, persist_other_seq_set, mech_seq_set
        persist_self_seq_set: persist the seq only but not others
        persist_other_seq_set: persist others but not this seq
        mech_seq_set: all seqs involved in mechanisms
        If we trust the invariant checks, does not still need the crash plans to check whether the corresponding recovery process works?
        '''

        # the seq set for mechanisms. Only persist itself, and only persist others.
        persist_self_seq_set : set = set()
        persist_other_seq_set : set = set()
        # the seqs that involved in all mech, the caller can select to generate crash plans or not.
        # this seqs is the super set of persist self and persist other
        mech_seq_set : set = set()

        if self.undojnl_reason:
            for jnl_entry in self.undojnl_reason.entry_list:
                jnl_entry : MechUndoJnlEntry
                mech_seq_set |= jnl_entry.get_all_seq()
                if check_unsafe:
                    # add the unsafe cases for checking to break the invariant
                    persist_other_seq_set.update(jnl_entry.unsafe_pother_set)
                    persist_self_seq_set.update(jnl_entry.unsafe_pself_set)
                if check_recovery:
                    # persist other but not the head update to check if the journal recovery works
                    if jnl_entry.head_store:
                        persist_other_seq_set.add(jnl_entry.head_store.op.seq)
                    elif jnl_entry.tx_commit_store:
                        persist_other_seq_set.add(jnl_entry.tx_commit_store.op.seq)

        if self.rep_reason:
            for rep_entry in self.rep_reason.entry_list:
                rep_entry : MechReplEntry
                mech_seq_set |= rep_entry.get_all_seq()
                if check_unsafe:
                    # add the unsafe cases for checking to break the invariant
                    persist_other_seq_set.update(rep_entry.unsafe_pother_set)
                    persist_self_seq_set.update(rep_entry.unsafe_pself_set)
                if check_recovery:
                    # persist others but not the memcpy to see if the recovery can see replication mismatch and sync them in correct order.
                    # Persist the memcpy itself and sampling it to see if the partial copy can be detected.
                    if rep_entry.store_op:
                        persist_other_seq_set.add(rep_entry.store_op.op_st.seq)
                        persist_self_seq_set.add(rep_entry.store_op.op_st.seq)

        # LSW updates are atomic, does not need to check the recovery.
        # however, we still need to get the seq protected by lsw
        if self.lsw_reason_list and len(self.lsw_reason_list) > 0:
            for lsw_reason in self.lsw_reason_list:
                lsw_reason : MechLSWReason
                for lsw_entry in lsw_reason.entry_list:
                    lsw_entry : MechLSWEntry
                    mech_seq_set |= lsw_entry.get_all_seq()

        return persist_self_seq_set, persist_other_seq_set, mech_seq_set
