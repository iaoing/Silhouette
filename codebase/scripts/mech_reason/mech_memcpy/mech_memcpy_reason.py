import os
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.mech_reason.mech_memcpy.mech_memcpy_entry import MechMemcpyEntry
from scripts.utils.logger import global_logger

class MechMemcpyReason:
    def __init__(self, split_entry : OpTraceEntry) -> None:
        self.entry_list = []
        # use for indexing, from src/dst address to a list of entries (since one src/dst might copy multiple times)
        self.src_addr_dict = dict()
        self.dst_addr_dict = dict()

        self.__init(split_entry)
        self.__init_mech_id()

    @property
    def entries(self):
        return self.entry_list

    def find_by_dst_addr(self, addr) -> list:
        if addr in self.dst_addr_dict:
            return self.dst_addr_dict[addr]
        else:
            return None

    def __init(self, split_entry : OpTraceEntry):
        pm_addr = split_entry.pm_addr
        pm_size = split_entry.pm_size
        memcpy_pairs = dict()
        for seq, entry_list in split_entry.seq_entry_map.items():
            for op in entry_list:
                op : TraceEntry

                if op.type.isMemTransLoad():
                    if op.seq not in memcpy_pairs:
                        memcpy_pairs[op.seq] = [None, None]
                    memcpy_pairs[op.seq][0] = op

                elif op.type.isMemTransStore():
                    if op.seq - 1 not in memcpy_pairs:
                        memcpy_pairs[op.seq - 1] = [None, None]
                    memcpy_pairs[op.seq - 1][1] = op

        for _, pair in memcpy_pairs.items():
            if not pair[0] or not pair[1]:
                log_msg = "no pair for memcpy load or store, %s, %s" % (str(pair[0]), str(pair[1]))
                global_logger.warning(log_msg)
            else:
                entry = MechMemcpyEntry(pair[0], pair[1], pm_addr, pm_size)
                self.entry_list.append(entry)

        for entry in self.entry_list:
            entry : MechMemcpyEntry
            src_addr = entry.src_addr
            dst_addr = entry.dst_addr
            if src_addr not in self.src_addr_dict:
                self.src_addr_dict[src_addr] = []
            if dst_addr not in self.dst_addr_dict:
                self.dst_addr_dict[dst_addr] = []
            self.src_addr_dict[src_addr].append(entry)
            self.dst_addr_dict[dst_addr].append(entry)

        global_logger.debug("src_addr_dict: " + str(self.src_addr_dict.items()))
        global_logger.debug("dst_addr_dict: " + str(self.dst_addr_dict.items()))

    def __init_mech_id(self):
        num = 0
        for entry in self.entry_list:
            num += 1
            entry.mech_id = num

    def dbg_get_detail(self):
        data = ""
        for entry in self.entry_list:
            entry : MechMemcpyEntry
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
