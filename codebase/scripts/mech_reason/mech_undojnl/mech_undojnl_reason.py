import os
import sys
import time
from intervaltree import Interval

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
from scripts.mech_reason.mech_store.mech_cirtical_pmstore_reason import MechCirticalPMStoreReason
from scripts.mech_reason.mech_undojnl.mech_undojnl_entry import MechUndoJnlEntry, UndoJnlLoggingEntry, UndoJnlInvariantErrorType
from scripts.cheat_sheet.base.cheat_base import CheatSheetBase, UndoJnlCheatSheetBase
from scripts.cheat_sheet.base.computation_sheet import ComputationElement, ComputationSheet
from scripts.utils.utils import isOverlapping
from scripts.utils.const_var import POINTER_SIZE
from scripts.utils.logger import global_logger
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.mech_undojnl.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class MechUndoJnlReason:
    """
    With the based cheat sheet, we can easily identify the journal head/tail
    and the journal space used to log data.

    Below introduction are deprecated.
    How to identify a undo journal?
    1. find a pair of cirtical stores
    2. if they have the same old value and new value
    3. if the old value and new value represent PM physical address (virtual address cannot be used in recovery)
    4. if have stores written to the range between old value and new value
    5. if the major of stores is represented by the same data struct

    How to identify the journal range?
    All writes should be wrapped by the same kind of data struct (journal entry).
    Thus, we can try to find the struct name from address struct map by head and tail.
    Then try to find all writes that represented by this struct.
    1. circular buffer, no overflow
    2. circular buffer, overflow
    3. linked pages/buffers/entries, e.g., Linux kernel log, Apache log.
    """
    def __init__(self, op_entry : OpTraceEntry, pmstore_reason : MechPMStoreReason, undo_jnl_cheatsheet : UndoJnlCheatSheetBase) -> None:
        assert undo_jnl_cheatsheet, "cheat sheet is required."

        self.sheet = undo_jnl_cheatsheet

        # the computation of the head and tail are in the sheet

        # the transaction-related operations
        self.logged_addr_computation = ComputationSheet(self.sheet.logged_addr)
        self.logged_size_computation = ComputationSheet(self.sheet.logged_size)
        self.logged_data_computation = ComputationSheet(self.sheet.logged_data)
        self.logging_commit_computation = ComputationSheet(self.sheet.logging_commit) if self.sheet.logging_commit else None

        self.tx_commit_computation = ComputationSheet(self.sheet.tx_commit_var) if self.sheet.tx_commit_var else None

        self.entry_list = []

        self.__init_entries_from_sheet(op_entry, pmstore_reason)
        self.__init_mech_id()

    def __lookup_logging_writes(self, jnl_entry : MechUndoJnlEntry, pm_entry : MechPMStoreEntry, st_name, var_name):
        if st_name in self.sheet.log_entry_struct:
            if not jnl_entry.logging_entry_size:
                jnl_entry.logging_entry_size = pm_entry.op.stinfo_match.stinfo.size_bytes
            if pm_entry.op.stinfo_match.addr not in jnl_entry.logging_entry_map:
                jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr] = UndoJnlLoggingEntry()
                if self.logged_size_computation.is_pure_number:
                    jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_size = self.logged_size_computation.evaluate()
            jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logging_write_list.append(pm_entry)

            if log.debug:
                    msg = f"add logging writes: {pm_entry}"
                    log.global_logger.debug(msg)
            return True
        return False

    def __lookup_logged_addr(self, jnl_entry : MechUndoJnlEntry, pm_entry : MechPMStoreEntry, st_name, var_name):
        if self.logged_addr_computation.contain_var(st_name, var_name):
            self.logged_addr_computation.set_value(st_name, var_name, pm_entry.op.sv_entry.data, convert_from_bytes=True)
            if self.logged_addr_computation.is_finalized():
                if not jnl_entry.logging_entry_size:
                    jnl_entry.logging_entry_size = pm_entry.op.stinfo_match.stinfo.size_bytes
                if pm_entry.op.stinfo_match.addr not in jnl_entry.logging_entry_map:
                    jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr] = UndoJnlLoggingEntry()
                    if self.logged_size_computation.is_pure_number:
                        jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_size = self.logged_size_computation.evaluate()
                jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_addr = self.logged_addr_computation.evaluate()

                if log.debug:
                    msg = f"update logged addr: 0x{jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_addr}"
                    log.global_logger.debug(msg)
                return True
        return False

    def __lookup_logged_size(self, jnl_entry : MechUndoJnlEntry, pm_entry : MechPMStoreEntry, st_name, var_name):
        if self.logged_size_computation.is_pure_number:
            # if it is a pure number, the size has been set when create the new obj
            return False
        if self.logged_size_computation.contain_var(st_name, var_name):
            self.logged_size_computation.set_value(st_name, var_name, pm_entry.op.sv_entry.data, convert_from_bytes=True)
            if log.debug:
                msg = f"logged size computation: {self.logged_size_computation}"
                log.global_logger.debug(msg)
            if self.logged_size_computation.is_finalized():
                if log.debug:
                    msg = f"finalized logged size computation: {self.logged_size_computation.evaluate()}"
                    log.global_logger.debug(msg)
                if not jnl_entry.logging_entry_size:
                    jnl_entry.logging_entry_size = pm_entry.op.stinfo_match.stinfo.size_bytes
                if pm_entry.op.stinfo_match.addr not in jnl_entry.logging_entry_map:
                    jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr] = UndoJnlLoggingEntry()
                jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_size = self.logged_size_computation.evaluate()

                if log.debug:
                    msg = f"update logged size: {jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_size}"
                    log.global_logger.debug(msg)
                return True
        else:
            if log.debug:
                msg = f"logged size does not match: {st_name}.{var_name}, {self.logged_size_computation}"
                log.global_logger.debug(msg)
        return False

    def __lookup_logged_data(self, jnl_entry : MechUndoJnlEntry, pm_entry : MechPMStoreEntry, st_name, var_name):
        if self.logged_data_computation.contain_var(st_name, var_name):
            # data is not an integer, do not need to evaluate
            if not jnl_entry.logging_entry_size:
                jnl_entry.logging_entry_size = pm_entry.op.stinfo_match.stinfo.size_bytes
            if pm_entry.op.stinfo_match.addr not in jnl_entry.logging_entry_map:
                jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr] = UndoJnlLoggingEntry()
                if self.logged_size_computation.is_pure_number:
                    jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_size = self.logged_size_computation.evaluate()
            jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logging_data_list.append(pm_entry)

            if log.debug:
                msg = f"update logged data write: {pm_entry}"
                log.global_logger.debug(msg)
            return True
        return False

    def __lookup_tx_commit(self, jnl_entry : MechUndoJnlEntry, pm_entry : MechPMStoreEntry, st_name, var_name):
        if not self.tx_commit_computation:
            return False

        if self.tx_commit_computation.contain_var(st_name, var_name):
            self.tx_commit_computation.set_value(st_name, var_name, pm_entry.op.sv_entry.data, convert_from_bytes=True)
            if log.debug:
                msg = f"tx commit computation: {self.tx_commit_computation}"
                log.global_logger.debug(msg)
            if self.tx_commit_computation.is_finalized():
                if log.debug:
                    msg = f"finalized tx commit computation: {self.tx_commit_computation.evaluate()}"
                    log.global_logger.debug(msg)
                if not jnl_entry.logging_entry_size:
                    jnl_entry.logging_entry_size = pm_entry.op.stinfo_match.stinfo.size_bytes
                if pm_entry.op.stinfo_match.addr not in jnl_entry.logging_entry_map:
                    jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr] = UndoJnlLoggingEntry()
                tx_commit_var_val = self.tx_commit_computation.evaluate()
                if tx_commit_var_val == self.sheet.tx_commit_var_val:
                    if log.debug:
                        msg = f"update tx commit write: {pm_entry}"
                        log.global_logger.debug(msg)
                    return True
        return False

    def __lookup_log_commit(self, jnl_entry : MechUndoJnlEntry, pm_entry : MechPMStoreEntry, st_name, var_name):
        if self.logging_commit_computation == None:
            return False

        if self.logging_commit_computation.contain_var(st_name, var_name):
            # commit is not an integer, do not need to evaluate
            if not jnl_entry.logging_entry_size:
                jnl_entry.logging_entry_size = pm_entry.op.stinfo_match.stinfo.size_bytes
            # the loggin commit should be a member variable of the log entry, and taking effect to only this logging entry
            if pm_entry.op.stinfo_match.addr not in jnl_entry.logging_entry_map:
                jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr] = UndoJnlLoggingEntry()
                if self.logged_size_computation.is_pure_number:
                    jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logged_size = self.logged_size_computation.evaluate()
            jnl_entry.logging_entry_map[pm_entry.op.stinfo_match.addr].logging_commit_list.append(pm_entry)

            if log.debug:
                msg = f"update log commit write: {pm_entry}"
                log.global_logger.debug(msg)
            return True
        return False

    def __lookup_inplace_write(self, jnl_entry : MechUndoJnlEntry, pm_entry : False, check_commit : bool):
        ret = False
        for _, logging_entry in jnl_entry.logging_entry_map.items():
            logging_entry : UndoJnlLoggingEntry
            if logging_entry.logged_size == 0:
                # this entry may be a commit entry, like the entry in PMFS and WineFS.
                continue
            if check_commit and len(logging_entry.logging_commit_list) != 1:
                # no commit writes
                continue
            if check_commit and pm_entry.op.seq < logging_entry.logging_commit_list[0].op.seq:
                continue
            if logging_entry.logged_addr and logging_entry.logged_size and isOverlapping([logging_entry.logged_addr, logging_entry.logged_addr + logging_entry.logged_size - 1], [pm_entry.phy_addr, pm_entry.phy_addr + pm_entry.size - 1]):
                # added if overlaps. We fill report it as an error if it is not a fully containess later.
                logging_entry.in_place_write_list.append(pm_entry)

                if log.debug:
                    msg = f"update in-place write: {pm_entry}"
                    log.global_logger.debug(msg)
                ret = True
        return ret

    @timeit
    def __init_entries_from_sheet(self, op_entry : OpTraceEntry,
                                  pmstore_reason : MechPMStoreReason):
        jnl_entry : MechUndoJnlEntry = MechUndoJnlEntry()
        jnl_entry.pm_addr = op_entry.pm_addr
        jnl_entry.pre_alloc = self.sheet.pre_alloc
        jnl_entry.phy_old_head_addr = self.sheet.head_computation.evaluate()
        jnl_entry.phy_old_tail_addr = self.sheet.tail_computation.evaluate()

        if log.debug:
            msg = f"begining of __init_entries_from_sheet: 0x{jnl_entry.phy_old_head_addr:x}, 0x{jnl_entry.phy_old_tail_addr:x}"
            log.global_logger.debug(msg)

        tx_started = False
        for pm_entry in pmstore_reason.entry_list:
            pm_entry : MechPMStoreEntry
            if pm_entry.op.stinfo_match == None:
                if log.debug:
                    msg = f"this PM store does not have matched structures: {pm_entry.op}"
                    log.global_logger.debug(msg)
                continue

            single_matched_variable = True
            if len(pm_entry.op.var_list) != 1:
                single_matched_variable = False
                if log.debug:
                    msg = f"this PM store matches more than one structure variables: {pm_entry.op.stinfo_match} {pm_entry.op.var_list}"
                    log.global_logger.debug(msg)
                continue

            st_name = pm_entry.op.stinfo_match.stinfo.struct_name
            var_name = pm_entry.op.var_list[0].var_name

            if not tx_started:
                if self.sheet.pre_alloc:
                    if single_matched_variable and self.sheet.update_tail(pm_entry.op):
                        # update tail to pre-allocate the log space for a journaling
                        # TODO: handle the wrap-around of the circular buffer
                        jnl_entry.phy_new_tail_addr = self.sheet.tail_computation.evaluate()
                        jnl_entry.tail_store = pm_entry
                        tx_started = True
                        if log.debug:
                            msg = f"update tail: 0x{jnl_entry.phy_new_tail_addr:x}"
                            log.global_logger.debug(msg)
                else:
                    # the logging writes indicate the beginning of the journaling
                    if single_matched_variable and self.__lookup_logging_writes(jnl_entry, pm_entry, st_name, var_name):
                        tx_started = True
                        # addr, size, and data should be a part of the logging writes
                        self.__lookup_logged_addr(jnl_entry, pm_entry, st_name, var_name)
                        self.__lookup_logged_size(jnl_entry, pm_entry, st_name, var_name)
                        self.__lookup_logged_data(jnl_entry, pm_entry, st_name, var_name)
            else:
                if single_matched_variable and self.sheet.update_tail(pm_entry.op):
                    # if is not pre-alloc, the tail update indicates the logging commit
                    jnl_entry.phy_new_tail_addr = self.sheet.tail_computation.evaluate()
                    jnl_entry.tail_store = pm_entry
                    if log.debug:
                        msg = f"update tail: 0x{jnl_entry.phy_new_tail_addr:x}"
                        log.global_logger.debug(msg)

                if self.__lookup_logging_writes(jnl_entry, pm_entry, st_name, var_name):
                    if single_matched_variable:
                        # addr, size, and data should be a part of the logging writes
                        self.__lookup_logged_addr(jnl_entry, pm_entry, st_name, var_name)
                        self.__lookup_logged_size(jnl_entry, pm_entry, st_name, var_name)
                        self.__lookup_logged_data(jnl_entry, pm_entry, st_name, var_name)

                if single_matched_variable and self.__lookup_log_commit(jnl_entry, pm_entry, st_name, var_name):
                    # this store has been added to the commit list, no more processes needed
                    pass

                if single_matched_variable and self.sheet.update_head(pm_entry.op):
                    jnl_entry.phy_new_head_addr = self.sheet.head_computation.evaluate()
                    jnl_entry.head_store = pm_entry
                    self.entry_list.append(jnl_entry)
                    tx_started = False
                    if log.debug:
                        msg = f"update head: 0x{jnl_entry.phy_new_head_addr:x}"
                        log.global_logger.debug(msg)

                    # make a new journal entry for the next tx.
                    # conceptually, each file-system operation only has one journal tx.
                    jnl_entry : MechUndoJnlEntry = MechUndoJnlEntry()
                    jnl_entry.pm_addr = op_entry.pm_addr
                    jnl_entry.phy_old_tail_addr = self.sheet.tail_computation.evaluate()
                    jnl_entry.phy_old_head_addr = self.sheet.head_computation.evaluate()

                elif single_matched_variable and self.__lookup_tx_commit(jnl_entry, pm_entry, st_name, var_name):
                    # PMFS and WineFS does not update the tail after a tx. Instead, they have a commit type to indicate the tx ends.
                    jnl_entry.phy_new_head_addr = jnl_entry.phy_new_tail_addr
                    jnl_entry.tx_commit_store = pm_entry

                    # NOTE: PMFS and WineFS update the gen_id after the commit type, it is complicatied to consider that situation that more than one journal tx in a function. Thus, we simply think each file-system function contains only one journal tx.
                    # self.entry_list.append(jnl_entry)
                    # tx_started = False
                    if log.debug:
                        msg = f"update head: 0x{jnl_entry.phy_new_head_addr:x}"
                        log.global_logger.debug(msg)

                    # make a new journal entry for the next tx.
                    # conceptually, each file-system operation only has one journal tx.
                    # jnl_entry : MechUndoJnlEntry = MechUndoJnlEntry()
                    # jnl_entry.pm_addr = op_entry.pm_addr
                    # jnl_entry.phy_old_tail_addr = self.sheet.tail_computation.evaluate()
                    # jnl_entry.phy_old_head_addr = jnl_entry.phy_old_tail_addr


        if (len(self.entry_list) == 0 or jnl_entry != self.entry_list[-1]) and (jnl_entry.tail_store != None or len(jnl_entry.logging_entry_map) > 0):
            self.entry_list.append(jnl_entry)

        # we only lookup the in-place writes that are issued after the logging commit and before the tx commit.
        # if the log space is pre-allocated, the commit write is a log structure entry write, otherwise, the tail update is the logging commit.
        # the tx commit is the head update.
        # if a tx does not have the commit or head update, we will not locate the in-place writes for it and report a bug later.
        for pm_entry in pmstore_reason.entry_list:
            pm_entry : MechPMStoreEntry
            # if log.debug:
            #     msg = f"pm store phy addr: [0x{pm_entry.phy_addr:x}, 0x{pm_entry.phy_addr+pm_entry.size:x}]"
            #     log.global_logger.debug(msg)
            for jnl_entry in self.entry_list:
                if not (jnl_entry.head_store or jnl_entry.tx_commit_store) or not jnl_entry.tail_store:
                    continue

                if not self.sheet.pre_alloc:
                    if pm_entry.op.seq > jnl_entry.tail_store.op.seq and pm_entry.op.seq < jnl_entry.head_store.op.seq:
                        self.__lookup_inplace_write(jnl_entry, pm_entry, check_commit=False)
                else:
                    if jnl_entry.tx_commit_store and pm_entry.op.seq < jnl_entry.tx_commit_store.op.seq:
                        self.__lookup_inplace_write(jnl_entry, pm_entry, check_commit=True)
                    elif jnl_entry.head_store and pm_entry.op.seq < jnl_entry.head_store.op.seq:
                        self.__lookup_inplace_write(jnl_entry, pm_entry, check_commit=True)

        if log.debug:
            msg = f"after init journal entries from {op_entry.op_name}\n{self.dbg_get_detail()}"
            log.global_logger.debug(msg)

    def __init_mech_id(self):
        num = 0
        for entry in self.entry_list:
            num += 1
            entry.mech_id = num

    @timeit
    def invariant_check(self):
        rst_list = []
        for jnl_entry in self.entry_list:
            jnl_entry : MechUndoJnlEntry
            rst_list += jnl_entry.invariant_check(check_data_match=True)
            if len(rst_list) > 0:
                msg = f"Invariant check failed: {rst_list}\n{jnl_entry.dbg_get_detail()}"
                log.global_logger.warning(msg)
        return rst_list

    def dbg_get_detail(self):
        data = ""
        for entry in self.entry_list:
            entry : MechUndoJnlEntry
            data += "Undo journal %d\n" % (entry.mech_id)
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
