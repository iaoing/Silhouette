import os
import sys
from enum import Enum



base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_entry
from scripts.utils.utils import isUserSpaceAddr, isKernelSpaceAddr
from scripts.mech_reason.mech_store.mech_pmstore_entry import MechPMStoreEntry
from scripts.utils.logger import global_logger

class MemsetType(Enum):
    SET_PM = 'set_pm',
    SET_KERNEL = 'set_kernel',
    SET_USER = 'set_user',

class MechMemsetEntry:
    def __init__(self, store : MechPMStoreEntry, pm_addr, pm_size) -> None:
        self.store : MechPMStoreEntry = store
        self.addr = None   # this is the virtual address
        self.size = None
        self.val = None    # 1 byte, int type, got from memoryview of bytes

        self.__init_vars()
        self.__init_type(pm_addr, pm_size)

    def get_opid_seq_list(self) -> list:
        return []

    def get_safe_data_seq_list(self) -> list:
        return []

    def get_unsafe_data_seq_list(self) -> list:
        return []

    def __init_vars(self):
        self.addr = self.store.op.addr
        self.size = self.store.op.size
        self.val = memoryview(self.store.op.sv_entry.data)[0]

    def __init_type(self, pm_addr, pm_size):
        if is_pm_entry(self.store.op, pm_addr, pm_size):
            self.type = MemsetType.SET_PM
        elif isKernelSpaceAddr(self.addr):
            self.type = MemsetType.SET_KERNEL
        else:
            self.type = MemsetType.SET_USER

    def dbg_get_detail(self):
        data = "type: %s, addr: %s, size: %s, val: %d\n" % (self.type, hex(self.addr), self.size, self.val)
        data += str(self.store)
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
