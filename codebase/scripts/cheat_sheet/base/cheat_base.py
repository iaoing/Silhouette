import os
import sys
import time
import traceback
from copy import deepcopy
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde
from pymemcache import MemcacheUnexpectedCloseError

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.cheat_sheet.base.computation_sheet import ComputationSheet
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry

class UndoJnlCheatSheetBase:
    def __init__(self):
        self.pre_alloc : bool = None

        # circular buffer size and address should be finalized in mount operation
        self.circular_buf_addr : list = None
        self.circular_buf_size : list = None
        self.buf_addr_computation : ComputationSheet= None
        self.buf_size_computation : ComputationSheet = None

        # head and tail should be tracked through each operation
        self.head : list = None
        self.tail : list = None
        self.head_computation : ComputationSheet = None
        self.tail_computation : ComputationSheet = None

        # PMFS and WineFS do not update the head after tx.
        # Thus, we need a sign to know the tx ends.
        self.tx_commit_var : list = None
        self.tx_commit_var_val : int = None

        # below information are the transaction-related
        self.log_entry_struct : list = None
        self.logged_addr : list = None
        self.logged_size : list = None
        self.logged_data :  list = None
        self.logging_commit : list = None

    def update_circular_buf_addr(self, trace_entry : TraceEntry):
        if not self.buf_addr_computation:
            self.buf_addr_computation = ComputationSheet(self.circular_buf_addr)

        if len(trace_entry.var_list) != 1 or trace_entry.stinfo_match == None or not trace_entry.sv_entry:
            return False

        st_name = trace_entry.stinfo_match.stinfo.struct_name
        var_name = trace_entry.var_list[0].var_name
        return self.buf_addr_computation.set_value(st_name, var_name, trace_entry.sv_entry.data, convert_from_bytes=True)

    def update_circular_buf_size(self, trace_entry : TraceEntry):
        if not self.buf_size_computation:
            self.buf_size_computation = ComputationSheet(self.circular_buf_size)

        if len(trace_entry.var_list) != 1 or trace_entry.stinfo_match == None or not trace_entry.sv_entry:
            return False

        st_name = trace_entry.stinfo_match.stinfo.struct_name
        var_name = trace_entry.var_list[0].var_name
        return self.buf_size_computation.set_value(st_name, var_name, trace_entry.sv_entry.data, convert_from_bytes=True)

    def update_head(self, trace_entry : TraceEntry):
        if not self.head_computation:
            self.head_computation = ComputationSheet(self.head)

        if len(trace_entry.var_list) != 1 or trace_entry.stinfo_match == None or not trace_entry.sv_entry:
            return False

        st_name = trace_entry.stinfo_match.stinfo.struct_name
        var_name = trace_entry.var_list[0].var_name
        return self.head_computation.set_value(st_name, var_name, trace_entry.sv_entry.data, convert_from_bytes=True)

    def update_tail(self, trace_entry : TraceEntry):
        if not self.tail_computation:
            self.tail_computation = ComputationSheet(self.tail)

        if len(trace_entry.var_list) != 1 or trace_entry.stinfo_match == None or not trace_entry.sv_entry:
            return False

        st_name = trace_entry.stinfo_match.stinfo.struct_name
        var_name = trace_entry.var_list[0].var_name
        return self.tail_computation.set_value(st_name, var_name, trace_entry.sv_entry.data, convert_from_bytes=True)

class LSWCheatSheetBase:
    def __init__(self):
        # the tail of the LSW
        self.tail : list = None
        ## different LSWs (e.g., inode_1's, inode_2's) have different locations
        self.tail_loc_to_computation_dict : dict = dict()
        # using a phoney computation to location the tail update.
        self.phoney_tail_computation : ComputationSheet = None

        # the size of one continuous log space, e.g., one page
        self.log_space_size : list = None
        self.log_space_size_computation : ComputationSheet = None

        # whether the log space require pre-allocate
        self.pre_alloc : bool = None

    def update_tail(self, trace_entry : TraceEntry):
        if not self.phoney_tail_computation:
            self.phoney_tail_computation = ComputationSheet(self.tail)

        if len(trace_entry.var_list) != 1 or trace_entry.stinfo_match == None or not trace_entry.sv_entry:
            return False, None, None

        st_name = trace_entry.stinfo_match.stinfo.struct_name
        var_name = trace_entry.var_list[0].var_name
        if not self.phoney_tail_computation.contain_var(st_name, var_name):
            return False, None, None

        tail_loc = trace_entry.addr
        if tail_loc not in self.tail_loc_to_computation_dict:
            self.tail_loc_to_computation_dict[tail_loc] = ComputationSheet(self.tail)

        old_tail_addr = None
        new_tail_addr = None

        curr_computation : ComputationSheet = self.tail_loc_to_computation_dict[tail_loc]
        if curr_computation.is_finalized():
            old_tail_addr = curr_computation.evaluate()

        curr_computation.set_value(st_name, var_name, trace_entry.sv_entry.data, convert_from_bytes=True)
        if curr_computation.is_finalized():
            if not old_tail_addr:
                # 0 is not a valid tail addr
                old_tail_addr = curr_computation.evaluate()
            else:
                new_tail_addr = curr_computation.evaluate()

        return True, old_tail_addr, new_tail_addr

    def update_log_space_size(self, trace_entry : TraceEntry):
        if not self.log_space_size_computation:
            self.log_space_size_computation = ComputationSheet(self.tail)

        if len(trace_entry.var_list) != 1 or trace_entry.stinfo_match == None or not trace_entry.sv_entry:
            return False

        st_name = trace_entry.stinfo_match.stinfo.struct_name
        var_name = trace_entry.var_list[0].var_name
        return self.log_space_size_computation.set_value(st_name, var_name, trace_entry.sv_entry.data, convert_from_bytes=True)


class RepCheatSheetBase:
    def __init__(self):
        # a list of structures that have replicas
        self.struct_set : set = None
        # number of replicas (includes the primary one)
        # TODO: only support 2 currently.
        self.num_rep : int = None

class LinkedListCheatSheetBase:
    def __init__(self):
        # a list of structure fields, which stores the pointer/address to the next entry
        # TODO: support offset
        self.next_fields : list = None

class CheatSheetBase:
    """docstring for CheatSheetBase."""
    def __init__(self):
        self.filesystem : str = None
        self.undo_jnl_sheet : UndoJnlCheatSheetBase = None
        # a list of LSWCheatSheetBase
        self.lsw_sheet_list : list = []
        self.rep_sheet : RepCheatSheetBase = None
        self.link_sheet : LinkedListCheatSheetBase = None
