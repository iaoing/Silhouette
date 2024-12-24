import os
import sys
from copy import deepcopy
import time
from intervaltree import Interval, IntervalTree

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_stinfo.addr_to_stinfo_entry import AddrToStInfoEntry
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_addr
from scripts.mech_reason.mech_store.mech_pmstore_entry import MechPMStoreEntry
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason
from scripts.mech_reason.mech_link.mech_link_reason import MechLinkEntry, MechLinkReason
from scripts.mech_reason.mech_lsw.mech_lsw_entry import MechLSWEntry
from scripts.cheat_sheet.base.computation_sheet import ComputationSheet
from scripts.cheat_sheet.base.cheat_base import LSWCheatSheetBase
from scripts.mech_reason.mech_undojnl.mech_undojnl_reason import MechUndoJnlReason, MechUndoJnlEntry, UndoJnlLoggingEntry
from scripts.mech_reason.mech_replication.mech_repl_reason import MechReplReason, MechReplEntry
from scripts.utils.const_var import POINTER_SIZE
from scripts.utils.logger import global_logger
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.mech_lsw.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper


class MechLSWReason:
    def __init__(self, op_entry : OpTraceEntry,
                 pmstore_reason : MechPMStoreReason,
                 link_reason : MechLinkReason,
                 undojnl_reason : MechUndoJnlReason,
                 rep_reason : MechReplReason,
                 cheat_sheet : LSWCheatSheetBase) -> None:
        # a list of MechLSWEntry
        self.entry_list = []
        self.sheet : LSWCheatSheetBase = cheat_sheet

        self.__init_entries(op_entry, pmstore_reason, link_reason, undojnl_reason, rep_reason)
        self.__init_mech_id()

    def __init_entries(self, op_entry : OpTraceEntry,
                       pmstore_reason : MechPMStoreReason,
                       link_reason : MechLinkReason,
                       undojnl_reason : MechUndoJnlReason,
                       rep_reason : MechReplReason):
        log_space_size : int = None

        # 1. locate the tail updates
        for pm_entry in pmstore_reason.entry_list:
            pm_entry : MechPMStoreEntry
            if pm_entry.op.stinfo_match == None:
                if log.debug:
                    msg = f"this PM store does not have matched structures: {pm_entry.op}"
                    log.global_logger.debug(msg)
                continue

            if len(pm_entry.op.var_list) != 1:
                if log.debug:
                    msg = f"this PM store matches more than one structure variables: {pm_entry.op.stinfo_match} {pm_entry.op.var_list}"
                    log.global_logger.debug(msg)
                continue

            if not log_space_size and self.sheet.update_log_space_size(pm_entry.op):
                log_space_size = self.sheet.log_space_size_computation.evaluate()

            old_tail_addr = new_tail_addr = None
            ret, old_tail_addr, new_tail_addr = self.sheet.update_tail(pm_entry.op)

            if log.debug:
                msg = f"lsw update tail: {ret} {old_tail_addr} {new_tail_addr}, {pm_entry.op.seq}, {pm_entry.op.var_list}"
                log.global_logger.debug(msg)

            if ret and old_tail_addr and new_tail_addr:
                lsw_entry = MechLSWEntry()
                lsw_entry.pre_alloc = self.sheet.pre_alloc
                lsw_entry.old_tail_addr = old_tail_addr
                lsw_entry.new_tail_addr = new_tail_addr
                lsw_entry.tail_store = pm_entry
                self.entry_list.append(lsw_entry)

        # 2. find all writes to the log space
        # 2.1 get all in-place writes of the journal.
        # Some writes to the log space could be updated inplace after persistence. This is safe if it is the in-place write of a journaling.
        safe_write_seq = set()
        for jnl_entry in undojnl_reason.entry_list:
            jnl_entry : MechUndoJnlEntry
            for logging_entry in jnl_entry.logging_entry_map.values():
                logging_entry : UndoJnlLoggingEntry
                safe_write_seq.update([x.op.seq for x in logging_entry.in_place_write_list])

        # 2.1 get all writes in replications.
        # Some writes to the log space could be updated inplace after persistence. This is safe if it has replications.
        for rep_entry in rep_reason.entry_list:
            rep_entry : MechReplEntry
            safe_write_seq.add(rep_entry.store_op.op_st.seq)
            safe_write_seq.update([x.op.seq for x in rep_entry.stores_to_primary_replica])

        # 2.3 locate these writes
        for lsw_entry in self.entry_list:
            lsw_entry : MechLSWEntry
            # address range for looking up the writes to the log space
            if log_space_size:
                if 0 < lsw_entry.new_tail_addr - lsw_entry.old_tail_addr < log_space_size:
                    lsw_entry.log_writes = pmstore_reason.get_entry_by_addr_seq_range(0, sys.maxsize, lsw_entry.old_tail_addr + op_entry.pm_addr, lsw_entry.new_tail_addr + op_entry.pm_addr)
                    lsw_entry.log_writes = [x for x in lsw_entry.log_writes if x.op.seq not in safe_write_seq]
                else:
                    # TODO: handling links of the log space
                    pass
            else:
                msg = f"invalid log space size: {log_space_size} for the lsw entry: {lsw_entry.dbg_get_detail()}"
                log.global_logger.error(msg)

    def __init_mech_id(self):
        num = 0
        for entry in self.entry_list:
            num += 1
            entry.mech_id = num

    @timeit
    def invariant_check(self):
        rst_list = []
        for lsw_entry in self.entry_list:
            lsw_entry : MechLSWEntry
            rst_list += lsw_entry.invariant_check()
            if len(rst_list) > 0:
                msg = f"LSW invariant check failed: {rst_list}\n{lsw_entry.dbg_get_detail()}"
                log.global_logger.warning(msg)
        return rst_list

    def dbg_get_detail(self):
        data = "LSW reason info:\n"
        for entry in self.entry_list:
            entry : MechLSWEntry
            data += "LSW %d\n" % (entry.mech_id)
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
