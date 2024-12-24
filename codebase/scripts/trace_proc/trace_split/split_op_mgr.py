"""
Split Operation trace.

E.g.,
trace: start_op1, xx, xx, end_op1, start_op2, xx, xx, end_op2, ...
entry_1: start_op1, xx, xx, end_op1
entry_1: start_op2, xx, xx, end_op2

The range of operations is determined by function annotation.
"""

import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from utils.logger import global_logger

class SplitOpMgr(object):
    """SplitOpMgr."""
    def __init__(self, trace_reader : TraceReader, vfs_op_info : SrcInfoReader):
        self.trace_reader = trace_reader
        self.vfs_op_info = vfs_op_info

        # We use a list to store all Op entries.
        # The list will be sorted by min seq after initialization.
        self.op_entry_list = list()

        self.__split_trace(trace_reader, vfs_op_info)
        self.op_entry_list.sort(key = lambda x : x.min_seq)

    def __split_trace(self, trace_reader : TraceReader, vfs_op_info : SrcInfoReader):
        first_mount = True
        for pid, seq_map in trace_reader.pid_seq_entry_map.items():
            op_entry = None

            for seq, entry_list in sorted(seq_map.items()):
                entry = entry_list[0]
                entry : TraceEntry

                # the pairs of function entries have been verified in trace reader.
                if op_entry == None and entry.fn_name in vfs_op_info and entry.type == TraceType.kStartFn:
                    op_entry = OpTraceEntry(entry, entry.fn_name, trace_reader.pm_addr, trace_reader.pm_size, pid)
                    op_entry.add_entry_list(entry_list, add_to_pm=True)
                    global_logger.debug("found new start function: %s" % (entry.fn_name))
                elif op_entry and TraceEntry.is_pair_func_entry(op_entry.start_fn_entry, entry):
                    op_entry.end_fn_entry = entry
                    op_entry.add_entry_list(entry_list, add_to_pm=True)
                    op_entry.finalize()
                    if first_mount and "fill_super" in op_entry.op_name:
                        first_mount = False
                        continue
                    self.op_entry_list.append(op_entry)
                    op_entry = None
                    global_logger.debug("found the end function: %s" % (entry.fn_name))
                elif op_entry:
                    op_entry.add_entry_list(entry_list, add_to_pm=True)
                else:
                    pass

    def analysis_in_cache_run(self, cache, clear_per_split):
        cache.write_back_all_stores()
        for entry in self.op_entry_list:
            entry.analysis_in_cache_run(cache)
            cache.write_back_all_stores()

    def debug_print_all(self):
        for op_entry in self.op_entry_list:
            op_entry.debug_print_all()
            print("\n")

    def debug_print_all_pm(self):
        for op_entry in self.op_entry_list:
            op_entry.debug_print_all_pm()
            print("\n")

    def debug_print_brief(self):
        for op_entry in self.op_entry_list:
            op_entry.debug_print_brief()
            print()

