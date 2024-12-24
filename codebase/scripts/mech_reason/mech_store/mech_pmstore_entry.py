import os
import sys
import time
from intervaltree import Interval, IntervalTree

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_entry, is_pm_addr
from scripts.utils.utils import isUserSpaceAddr, isKernelSpaceAddr, alignToFloor, alignToCeil, addrRangeToCachelineList
from scripts.utils.const_var import CACHELINE_BYTES
from scripts.utils.logger import global_logger
import scripts.utils.logger as log

class MechPMStoreEntry:
    '''all store that write data to PM, including memset, memcpy, store, etc.'''
    def __init__(self, op : TraceEntry, split_entry : OpTraceEntry) -> None:
        self.op : TraceEntry = op
        self.addr = None   # this is the virtual address
        self.size = None

        # the physical PM address
        self.phy_addr = None

        # which op flush and fence this store
        # could be a list, if it is flushed by more than one op
        self.flush_op = []
        self.fence_op : TraceEntry = None

        # this is the first fence after the update seq, it may not the same as the fence op
        # it can be used to determine the update order within a cache line
        self.first_fence_op : TraceEntry = None

        self.__init_vars(split_entry)

    def get_opid_seq_list(self) -> list:
        return [self.op.seq]

    def get_safe_data_seq_list(self) -> list:
        return []

    def get_unsafe_data_seq_list(self) -> list:
        return []

    def __str__(self) -> str:
        data = str(self.op)
        if self.flush_op:
            data += ", last flush at %d" % (self.flush_op[-1].seq)
        else:
            data += ", no flush"
        if self.fence_op:
            data += ", fence at %d" % (self.fence_op.seq)
        else:
            data += ", no fence "
        return data

    def __repr__(self) -> str:
        return self.__str__()

    def __member(self) -> tuple:
        return self.op.member()

    def __eq__(self, other) -> bool:
        if not isinstance(other, MechPMStoreEntry):
            return False
        return self.__member() == other.__member()

    def __hash__(self) -> int:
        return hash(self.__member())

    def __init_vars(self, split_entry : OpTraceEntry):
        self.addr = self.op.addr
        self.size = self.op.size
        self.phy_addr = self.addr - split_entry.pm_addr

    def init_flush(self, flush_list):
        iv_tree = IntervalTree()
        iv_tree[self.addr : self.addr + self.size] = ''

        for flush in flush_list:
            flush : TraceEntry

            if iv_tree.is_empty():
                break
            if flush.seq >= self.op.seq:
                if iv_tree[flush.addr : flush.addr + flush.size]:
                    iv_tree.chop(flush.addr, flush.addr + flush.size)
                    self.flush_op.append(flush)

        if len(self.flush_op) == 0:
            log_msg = "does not have a flush instruction, %s" % (str(self.op))
            global_logger.warning(log_msg)
        if len(iv_tree) > 0:
            log_msg = "does not find all flush instructions, %s, %s, %s" % (str(self.op), str(self.flush_op), str(iv_tree.items()))
            global_logger.warning(log_msg)
            self.flush_op = []

        self.flush_op.sort(key = lambda x: x.seq)

    def init_fence(self, fence_list):
        '''required: init flush first'''
        last_flush_seq = 0
        if len(self.flush_op) == 0:
            return
        else:
            last_flush_seq = self.flush_op[-1].seq

        for fence in fence_list:
            fence : TraceEntry
            if not self.first_fence_op and fence.seq >= self.op.seq:
                self.first_fence_op = fence
            if fence.seq >= last_flush_seq:
                self.fence_op = fence
                break

        if self.fence_op == None:
            log_msg = "does not have a fence instruction, %s" % (str(self.op))
            global_logger.warning(log_msg)

    @property
    def old_data(self) -> bytes:
        return self.op.ov_entry.data

    @property
    def new_data(self) -> bytes:
        return self.op.sv_entry.data

    def dbg_get_detail(self):
        flush_seq = None
        if len(self.flush_op) > 0:
            flush_seq = [x.seq for x in self.flush_op]

        fence_seq = None
        if self.fence_op != None:
            fence_seq = self.fence_op.seq

        data = "addr: %s, size: %s, flush seq: %s, fence seq: %s, first fence op: %s" % \
            (hex(self.addr), self.size, str(flush_seq), str(fence_seq), str(self.first_fence_op))
        if self.size <= 8:
            data += ", new data: %s, old data: %s\n" % (str(self.new_data), str(self.old_data))
        else:
            data += "\n"
        data += f"{self.op.var_list}, {str(self.op)}"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
