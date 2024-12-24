import os
import sys
from enum import Enum
from intervaltree import Interval, IntervalTree

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
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason
from scripts.utils.utils import alignToFloor
from scripts.utils.const_var import CACHELINE_BYTES
import scripts.utils.logger as log

class UndoJnlInvariantErrorType(Enum):
    """ The error types of undo journal invariants """
    NO_HEAD_UPDATE_OR_TX_COMMIT = 'no_head_update_or_tx_commit'
    NO_TAIL_UPDATE              = 'no_tail_update'
    NO_LOGGING_ENTRY            = 'no_logging_entry'
    NO_LOGGING_WRITE            = 'no_logging_write'
    NO_LOGGED_DATA              = 'no_logged_data'
    NO_LOGGING_COMMIT           = 'no_logging_commit'
    NO_IN_PLACE_WRITE           = 'no_in_place_write'

    TOO_MANY_LOGGED_DATA    = 'too_many_logged_data'
    TOO_MANY_LOGGING_COMMIT = 'too_many_logging_commit'

    LOGGING_WRITE_FENCED_AFTER_LOGGING_COMMIT  = 'logging_write_fenced_after_logging_commit'
    LOGGING_COMMIT_FENCED_AFTER_HEAD_UPDATE    = 'logging_commit_fenced_after_head_update'
    LOGGING_COMMIT_FENCED_AFTER_IN_PLACE_WRITE = 'logging_commit_fenced_after_in_place_write'
    IN_PLACE_WRITE_FENCED_AFTER_HEAD_UPDATE    = 'in_place_write_fenced_after_head_update'
    LOGGED_DATA_NOT_MATCH_IN_PLACE_WRITE      = 'logged_data_not_match_in_place_write'


class UndoJnlLoggingEntry:
    def __init__(self):
        # A list of MechPMStoreEntry of logging writes.
        # Logging writes contain logged data write
        # It may or may not contain the commit write. The commit write could be a variable in of the logging structure, it could also be a part of other structures.
        self.logging_write_list : list = []
        self.logged_addr : int = None # physical address
        self.logged_size : int = None
        # a list of MechPMStoreEntry
        self.logging_data_list : list = []
        # a list of MechPMStoreEntry
        self.logging_commit_list : list = []
        # a list of MechPMStoreEntry of in-place writes
        self.in_place_write_list : list = []

        # for invariant check and the dbg info
        self.logging_write_fenced_after_logging_commit_seq_set : set = set()

    def dbg_str(self):
        data = "UndoJnlLoggingEntry:\n"
        data += "logging writes:\n"
        for w in self.logging_write_list:
            data += f"seq: {w.op.seq}, fence seq: {w.fence_op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)}\n"
        data += "logging data writes:\n"
        for w in self.logging_data_list:
            data += f"{w.op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)}\n"
        data += "logging commits:\n"
        for w in self.logging_commit_list:
            data += f"{w.op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)}\n"
        if self.logged_addr and self.logged_size:
            data += f"logged addr and size: 0x{self.logged_addr:x}, {self.logged_size}\n"
        else:
            data += f"logged addr and size: {str(self.logged_addr)}, {str(self.logged_size)}\n"
        data += "logging in-place writes:\n"
        for w in self.in_place_write_list:
            if w.op.seq in self.logging_write_fenced_after_logging_commit_seq_set:
                data += f"{w.op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)} (logged data does not match the old content of this write)\n"
            else:
                data += f"{w.op.seq}, 0x{w.phy_addr:x}, {w.size}, {str(w.op.stinfo_match)}, {str(w.op.var_list)}\n"
        return data

class MechUndoJnlEntry:
    '''
    One Undo Journal Entry contains 4 phases of a journaling action.
    '''
    def __init__(self):
        self.mech_id = -1
        self.pre_alloc = None

        self.head_store : MechPMStoreEntry = None
        self.tail_store : MechPMStoreEntry = None
        self.tx_commit_store : MechPMStoreEntry = None

        # physical and virtual addresses of the journal space
        self.pm_addr : int = 0
        self.phy_old_head_addr : int = 0
        self.phy_new_head_addr : int = 0
        self.phy_old_tail_addr : int = 0
        self.phy_new_tail_addr : int = 0

        # the logging entry addr to UndoJnlLoggingEntry map
        self.logging_entry_map = dict()
        # the size of a logging entry
        self.logging_entry_size : int = 0

        # a list of seq that need to be persisted it only (2CP) to test
        self.unsafe_pself_set : set = set()
        # a list of seq that need to be persisted other only (2CP) to test
        self.unsafe_pother_set : set = set()

    def get_all_seq(self) -> set:
        seqs : set = set()
        if self.head_store:
            seqs.add(self.head_store.op.seq)
        if self.tail_store:
            seqs.add(self.tail_store.op.seq)
        if self.tx_commit_store:
            seqs.add(self.tx_commit_store.op.seq)
        for logging_entry in self.logging_entry_map.values():
            logging_entry : UndoJnlLoggingEntry
            seqs |= set([x.op.seq for x in logging_entry.logging_write_list])
            seqs |= set([x.op.seq for x in logging_entry.logging_data_list])
            seqs |= set([x.op.seq for x in logging_entry.logging_commit_list])
            seqs |= set([x.op.seq for x in logging_entry.in_place_write_list])
        return seqs

    def invariant_check(self, check_data_match : bool = False) -> list:
        '''
        Returns a list of invariant checking errors.
        Sometimes, we cannot conduct the data check (e.g., checking the logged data and the in-place writes have the same content). This is because some file systems do not log the content. For example, NOVA logs the address of the replica inode, so that we cannot compare them.
        '''
        err_list = []

        if not self.head_store and not self.tx_commit_store:
            err_list.append(UndoJnlInvariantErrorType.NO_HEAD_UPDATE_OR_TX_COMMIT)
            return err_list

        if not self.tail_store:
            err_list.append(UndoJnlInvariantErrorType.NO_TAIL_UPDATE)
            return err_list

        if len(self.logging_entry_map) == 0:
            err_list.append(UndoJnlInvariantErrorType.NO_LOGGING_ENTRY)
            return err_list

        else:
            for logging_entry in self.logging_entry_map.values():
                logging_entry : UndoJnlLoggingEntry
                logging_commit_pm_store : MechPMStoreEntry = None
                logged_data_pm_store : MechPMStoreEntry = None

                if self.pre_alloc:
                    if len(logging_entry.logging_commit_list) == 0:
                        err_list.append(UndoJnlInvariantErrorType.NO_LOGGING_COMMIT)
                        if log.debug:
                            msg = f"journal logging entry no logging commit: {logging_entry.dbg_str()}"
                            log.global_logger.debug(msg)

                    elif len(logging_entry.logging_commit_list) > 1:
                        err_list.append(UndoJnlInvariantErrorType.TOO_MANY_LOGGING_COMMIT)
                        if log.debug:
                            msg = f"journal logging entry too many logging commit: {logging_entry.dbg_str()}"
                            log.global_logger.debug(msg)

                    else:
                        logging_commit_pm_store = logging_entry.logging_commit_list[0]

                else:
                    logging_commit_pm_store = self.tail_store

                if not logging_commit_pm_store:
                    continue

                if self.head_store:
                    if logging_commit_pm_store.fence_op.seq > self.head_store.op.seq:
                        err_list.append(UndoJnlInvariantErrorType.LOGGING_COMMIT_FENCED_AFTER_HEAD_UPDATE)
                elif self.tx_commit_store:
                    if logging_commit_pm_store.fence_op.seq > self.tx_commit_store.op.seq:
                        err_list.append(UndoJnlInvariantErrorType.LOGGING_COMMIT_FENCED_AFTER_HEAD_UPDATE)

                if len(logging_entry.logging_write_list) == 0:
                    err_list.append(UndoJnlInvariantErrorType.NO_LOGGING_WRITE)
                else:
                    for w in logging_entry.logging_write_list:
                        w : MechPMStoreEntry
                        if alignToFloor(w.addr, CACHELINE_BYTES) == alignToFloor(logging_commit_pm_store.addr, CACHELINE_BYTES):
                            # if they are in the same cacheline, check if existing a fence between them
                            if w.op.seq != logging_commit_pm_store.op.seq and w.first_fence_op.seq > logging_commit_pm_store.op.seq:
                                err_list.append(UndoJnlInvariantErrorType.LOGGING_WRITE_FENCED_AFTER_LOGGING_COMMIT)
                                if log.debug:
                                    msg = f"logging write fence after logging commit even in the same cache line:\n{w.dbg_get_detail()}\n{logging_commit_pm_store.dbg_get_detail()}"
                                    log.global_logger.debug(msg)
                        else:
                            if log.debug:
                                msg = f"alignment check: {w.addr:x} -> {alignToFloor(w.addr, CACHELINE_BYTES):x}, {logging_commit_pm_store.addr:x} -> {alignToFloor(logging_commit_pm_store.addr, CACHELINE_BYTES):x}"
                                log.global_logger.debug(msg)

                            if w.op.seq != logging_commit_pm_store.op.seq and w.fence_op.seq > logging_commit_pm_store.op.seq:
                                err_list.append(UndoJnlInvariantErrorType.LOGGING_WRITE_FENCED_AFTER_LOGGING_COMMIT)
                                if log.debug:
                                    msg = f"logging write fence after logging commit: \n{w.dbg_get_detail()}\n{logging_commit_pm_store.dbg_get_detail()}"
                                    log.global_logger.debug(msg)

                if len(logging_entry.logging_data_list) == 0 or not logging_entry.logged_size or logging_entry.logged_size == 0:
                    continue
                elif len(logging_entry.logging_data_list) > 1:
                    err_list.append(UndoJnlInvariantErrorType.TOO_MANY_LOGGED_DATA)
                else:
                    logged_data_pm_store = logging_entry.logging_data_list[0]

                if len(logging_entry.in_place_write_list) == 0:
                    err_list.append(UndoJnlInvariantErrorType.NO_IN_PLACE_WRITE)
                else:
                    for w in logging_entry.in_place_write_list:
                        w : MechPMStoreEntry
                        if logging_commit_pm_store.op.seq != w.op.seq and logging_commit_pm_store.fence_op.seq > w.op.seq:
                            err_list.append(UndoJnlInvariantErrorType.LOGGING_COMMIT_FENCED_AFTER_IN_PLACE_WRITE)

                        if self.head_store:
                            if w.fence_op.seq >= self.head_store.op.seq:
                                err_list.append(UndoJnlInvariantErrorType.IN_PLACE_WRITE_FENCED_AFTER_HEAD_UPDATE)
                                logging_entry.logging_write_fenced_after_logging_commit_seq_set.add(w.op.seq)
                        elif self.tx_commit_store:
                            if w.fence_op.seq >= self.tx_commit_store.op.seq:
                                err_list.append(UndoJnlInvariantErrorType.IN_PLACE_WRITE_FENCED_AFTER_HEAD_UPDATE)
                                logging_entry.logging_write_fenced_after_logging_commit_seq_set.add(w.op.seq)

                        if check_data_match and logged_data_pm_store and logged_data_pm_store.op.size == logging_entry.logged_size:
                            offset = w.op.addr - self.pm_addr - logging_entry.logged_addr
                            if w.op.ov_entry.data != logged_data_pm_store.op.sv_entry.data[offset:offset+w.op.size]:
                                err_list.append(UndoJnlInvariantErrorType.LOGGED_DATA_NOT_MATCH_IN_PLACE_WRITE)
                                msg = f"logged data does not match in-place write's old data:\nlogged size: {logging_entry.logged_size}\n0x{w.op.addr - self.pm_addr:x}\n{w.op.ov_entry.to_str_full(w.size)}\n0x{logging_entry.logged_addr:x}\n{logged_data_pm_store.op.sv_entry.to_str_full(logged_data_pm_store.size)}\n{w.dbg_get_detail()}\n{logging_entry.dbg_str()}\n"
                                log.global_logger.error(msg)

        return err_list

    def dbg_get_detail(self):
        data = f"MechUndoJnlEntry:\nhead store: {self.head_store}\ntail store: {self.tail_store}\ntx_commit: {self.tx_commit_store}\nhead and tail: [0x{self.phy_old_head_addr:x}, 0x{self.phy_old_tail_addr:x}] -> [0x{self.phy_new_head_addr:x}, 0x{self.phy_new_tail_addr:x}]\n"
        for _, logging_entry in self.logging_entry_map.items():
            data += logging_entry.dbg_str() + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
