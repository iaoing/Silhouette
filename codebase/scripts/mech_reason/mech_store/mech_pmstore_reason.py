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
from scripts.mech_reason.mech_store.mech_pmstore_entry import MechPMStoreEntry
from scripts.utils.logger import global_logger
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.mech_pmstore.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class MechPMStoreReason:
    def __init__(self, split_entry : OpTraceEntry) -> None:
        self.entry_list = []
        self.entry_dict = dict()

        # addr to pmstore entry
        self.iv_tree = IntervalTree()

        self.__init(split_entry)

    @timeit
    def __init(self, split_entry : OpTraceEntry):
        flush_list = []
        fence_list = []

        for seq in split_entry.pm_sorted_seq:
            for op in split_entry.pm_seq_entry_map[seq]:
                op : TraceEntry

                if op.type.isStoreSeries():
                    entry = MechPMStoreEntry(op, split_entry)
                    self.entry_list.append(entry)
                    if op.seq not in self.entry_dict:
                        self.entry_dict[op.seq] = []
                    self.entry_dict[op.seq].append(entry)
                    self.iv_tree[op.addr : op.addr + op.size] = set([entry])
                if op.type.isFlushTy():
                    flush_list.append(op)
                if op.type.isFenceTy():
                    fence_list.append(op)

        log_msg = "%s flush seq list: %s" % (split_entry.op_name, str([x.seq for x in flush_list]))
        global_logger.debug(log_msg)
        log_msg = "%s fence seq list: %s" % (split_entry.op_name, str([x.seq for x in fence_list]))
        global_logger.debug(log_msg)

        for entry in self.entry_list:
            entry : MechPMStoreEntry
            entry.init_flush(flush_list)
            entry.init_fence(fence_list)
            log_msg = str(entry)
            global_logger.debug(log_msg)

    def get_entry_by_seq(self, seq):
        if seq in self.entry_dict:
            return self.entry_dict[seq]
        return None

    def get_entry_set_by_addr(self, addr):
        rst = set()
        for iv in self.iv_tree.at(addr):
            rst |= iv.data
        return rst

    def get_entry_by_addr_seq_range(self, seq1, seq2, addr1, addr2) -> list:
        candidates = set()
        for iv in self.iv_tree[addr1 : addr2]:
            candidates |= iv.data

        rst = []
        for entry in candidates:
            entry : MechPMStoreEntry
            if seq1 <= entry.op.seq <= seq2:
                rst.append(entry)
        return rst

    def dbg_get_brief(self):
        data = ""
        for entry in self.entry_list:
            data += entry.op.__str__().rstrip() + "\n"
        return data

    def dbg_print_brief(self):
        print(self.dbg_get_brief())

    def dbg_get_detail(self):
        data = ""
        for entry in self.entry_list:
            entry : MechPMStoreEntry
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
