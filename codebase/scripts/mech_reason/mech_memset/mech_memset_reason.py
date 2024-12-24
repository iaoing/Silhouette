import os
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason
from scripts.mech_reason.mech_memset.mech_memset_entry import MechMemsetEntry
from scripts.utils.logger import global_logger

class MechMemsetReason:
    def __init__(self, split_entry : OpTraceEntry, pmstore_reason : MechPMStoreReason) -> None:
        self.entry_list = []

        self.__init(split_entry, pmstore_reason)
        self.__init_mech_id()

    def __init(self, split_entry : OpTraceEntry, pmstore_reason : MechPMStoreReason):
        for seq in split_entry.pm_sorted_seq:
            for op in split_entry.pm_seq_entry_map[seq]:
                op : TraceEntry

                if op.type.isMemset():
                    store = pmstore_reason.get_entry_by_seq(op.seq)
                    if store == None or len(store) > 1:
                        err_msg = "found nothing or more than one pm store for a store trace, %s, %s\n%s" \
                            % (str(op), str(store), pmstore_reason.dbg_get_detail())
                        global_logger.error(err_msg)
                        assert False, err_msg

                    entry = MechMemsetEntry(store[0], split_entry.pm_addr, split_entry.pm_size)
                    self.entry_list.append(entry)

    def __init_mech_id(self):
        num = 0
        for entry in self.entry_list:
            num += 1
            entry.mech_id = num

    def dbg_get_detail(self):
        data = ""
        for entry in self.entry_list:
            entry : MechMemsetEntry
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
