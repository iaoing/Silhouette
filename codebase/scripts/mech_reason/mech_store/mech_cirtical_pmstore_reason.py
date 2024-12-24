import os
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.mech_reason.mech_store.mech_pmstore_entry import MechPMStoreEntry
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason
from scripts.utils.const_var import ATOMIC_WRITE_BYTES
from scripts.utils.logger import global_logger

class MechCirticalPMStoreReason:
    """Cirtical store does not a dedicated entry, it can use pm store entry"""
    def __init__(self, split_entry : OpTraceEntry, pmstore_reason : MechPMStoreReason = None) -> None:
        if pmstore_reason == None:
            pmstore_reason = MechPMStoreReason(split_entry)
        self.pmstore_reason = pmstore_reason

        self.entry_list = []

        self.__init(split_entry)

    def __init(self, split_entry : OpTraceEntry):
        seq_list = []
        last_op_is_fence = True

        for i in range(len(split_entry.pm_sorted_seq)):
            seq = split_entry.pm_sorted_seq[i]
            op = split_entry.pm_seq_entry_map[seq][0]
            op : TraceEntry

            if last_op_is_fence == False:
                # if last op is not fence, does not need to check further
                last_op_is_fence = op.type.isFenceTy()
                continue

            if op.type.isStoreSeries() and op.size <= ATOMIC_WRITE_BYTES:
                # size larger than ATOMIC_WRITE_BYTES cannot be an atomic write

                # check if next operation is the flush of the op
                flush_in_next = False
                if i + 1 < len(split_entry.pm_sorted_seq):
                    flush_seq = split_entry.pm_sorted_seq[i + 1]
                    flush_op : TraceEntry = split_entry.pm_seq_entry_map[flush_seq][0]
                    if flush_op.type.isFlushTy() and \
                            flush_op.addr <= op.addr and \
                            op.addr + op.size <= flush_op.addr + flush_op.size:
                        flush_in_next = True

                if flush_in_next == False:
                    continue

                # check if the next next operation is the fence operation
                fence_in_next = False
                pos = i + 2
                while True and pos < len(split_entry.pm_sorted_seq):
                    fence_seq = split_entry.pm_sorted_seq[pos]
                    flush_op : TraceEntry = split_entry.pm_seq_entry_map[fence_seq][0]
                    if flush_op.type.isFlushTy():
                        # TODO: extra flush does not affect the concept of critical store
                        pos += 1
                    elif flush_op.type.isFenceTy():
                        fence_in_next = True
                        break
                    else:
                        break

                if i + 2 < len(split_entry.pm_sorted_seq):
                    fence_seq = split_entry.pm_sorted_seq[i + 2]
                    flush_op : TraceEntry = split_entry.pm_seq_entry_map[fence_seq][0]
                    if flush_op.type.isFenceTy():
                        fence_in_next = True
                else:
                    # if reach the end of the split entry, as true
                    fence_in_next = True

                if flush_in_next and fence_in_next:
                    seq_list.append(op.seq)

        global_logger.debug(str(seq_list))

        for entry in self.pmstore_reason.entry_list:
            entry : MechPMStoreEntry
            if entry.op.seq in seq_list:
                self.entry_list.append(entry)

    def dbg_get_detail(self):
        data = ""
        for entry in self.entry_list:
            entry : MechPMStoreEntry
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
