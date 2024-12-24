import os
import sys
from enum import Enum

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_entry, is_pm_addr
from scripts.utils.utils import isUserSpaceAddr, isKernelSpaceAddr
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex, StructInfo, AddrToStInfoEntry, StructMemberVar
from scripts.mech_reason.mech_store.mech_pmstore_entry import MechPMStoreEntry
from scripts.mech_reason.mech_undojnl.mech_undojnl_reason import MechUndoJnlReason, MechUndoJnlEntry, UndoJnlLoggingEntry
import scripts.utils.logger as log

class LSWInvariantErrorType(Enum):
    LOG_WRITES_INCORRECT_PERSISTENCE_TIME = 'log_writes_incorrect_persistence_time'

class MechLSWEntry:
    def __init__(self):
        self.pre_alloc = None
        # old and new tail physical address
        self.old_tail_addr : int = None
        self.new_tail_addr : int = None

        # the store that updates this tail from old to new
        self.tail_store : MechPMStoreEntry = None

        # a list of MechPMStoreEntry
        self.log_writes : list = []

        # to store the invariant check error disk, seq to error type
        self.err_dict : dict = dict()

    def __str__(self) -> str:
        data = ""
        data += str(self.tail_store)
        return data

    def __repr__(self) -> str:
        return self.__str__()

    def get_all_seq(self) -> set:
        seqs : set = set()
        if self.tail_store:
            seqs.add(self.tail_store.op.seq)
        for w in self.log_writes:
            seqs.add(w.op.seq)
        return seqs

    def invariant_check(self):
        self.err_dict.clear()
        if self.pre_alloc:
            # if the log space need to pre-allocate, the log writes are issued after the tail persisted.
            for w in self.log_writes:
                w : MechPMStoreEntry
                if w.op.seq <= self.tail_store.fence_op.seq:
                    msg = f"lsw check failed (pre_alloc):\n"
                    msg += f"tail store: update seq: {self.tail_store.op.seq}, fence seq: {self.tail_store.fence_op.seq}, {str(self.tail_store.op.stinfo_match)}, {str(self.tail_store.op.var_list)}\n"
                    msg += f"update seq: {w.op.seq}, fence seq: {w.fence_op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)}\n"
                    log.global_logger.warning(msg)
                    self.err_dict[w.op.seq] = LSWInvariantErrorType.LOG_WRITES_INCORRECT_PERSISTENCE_TIME
        else:
            # if the log space is not pre-allocated, the log writes should be persisted before the tail update.
            for w in self.log_writes:
                w : MechPMStoreEntry
                if w.fence_op.seq >= self.tail_store.op.seq:
                    msg = f"lsw check failed:\n"
                    msg += f"tail store: update seq: {self.tail_store.op.seq}, fence seq: {self.tail_store.fence_op.seq}, {str(self.tail_store.op.stinfo_match)}, {str(self.tail_store.op.var_list)}\n"
                    msg += f"update seq: {w.op.seq}, fence seq: {w.fence_op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)}\n"
                    log.global_logger.warning(msg)
                    self.err_dict[w.op.seq] = LSWInvariantErrorType.LOG_WRITES_INCORRECT_PERSISTENCE_TIME
        return list(self.err_dict.values())

    def dbg_get_detail(self):
        data = ''
        data += f"old tail: 0x{self.old_tail_addr:x}, new tail: 0x{self.new_tail_addr:x}\n"
        data += f"tail store: update seq: {self.tail_store.op.seq}, fence seq: {self.tail_store.fence_op.seq}, {str(self.tail_store.op.stinfo_match)}, {str(self.tail_store.op.var_list)}, {str(self.tail_store.op.src_entry)}\n"
        for w in self.log_writes:
            data += f"update seq: {w.op.seq}, fence seq: {w.fence_op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)}, {str(w.op.src_entry)}"
            if w.op.seq in self.err_dict:
                data += f" ({self.err_dict[w.op.seq]})\n"
            else:
                data += "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
