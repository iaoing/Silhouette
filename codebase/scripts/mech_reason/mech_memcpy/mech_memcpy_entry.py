import os
import sys
from enum import Enum

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_entry, is_pm_addr
from scripts.utils.utils import isUserSpaceAddr, isKernelSpaceAddr
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason, MechPMStoreEntry
from scripts.utils.logger import global_logger

class MemcpyType(Enum):
    PM_TO_PM         = 'pm_to_pm',
    PM_TO_KERNEL     = 'pm_to_kernel',
    PM_TO_USER       = 'pm_to_user',
    KERNEL_TO_PM     = 'kernel_to_pm',
    KERNEL_TO_KERNEL = 'kernel_to_kernel',
    KERNEL_TO_USER   = 'kernel_to_user',
    USER_TO_PM       = 'user_to_pm',
    USER_TO_KERNEL   = 'user_to_kernel',
    USER_TO_USER     = 'user_to_user',
    UNKNOWN          = 'unknown'

    def is_to_pm(self):
        return any(self is x for x in [MemcpyType.PM_TO_PM, MemcpyType.KERNEL_TO_PM, MemcpyType.USER_TO_PM])

    def is_from_pm(self):
        return any(self is x for x in [MemcpyType.PM_TO_PM, MemcpyType.PM_TO_KERNEL, MemcpyType.PM_TO_USER])

    def is_pm_related(self):
        return any(self is x for x in [MemcpyType.PM_TO_PM, MemcpyType.PM_TO_KERNEL, MemcpyType.PM_TO_USER, MemcpyType.KERNEL_TO_PM, MemcpyType.USER_TO_PM])

class MechMemcpyEntry:
    def __init__(self, op_ld : TraceEntry, op_st : TraceEntry, pm_addr, pm_size) -> None:
        assert op_ld.size == op_st.size, "invalid memcpy traces, %s, %s" % (str(op_ld), str(op_st))

        self.type : MemcpyType = MemcpyType.UNKNOWN
        # in tracing, we separate memcpy as two traces, one is source, another is destination.
        self.op_ld : TraceEntry = op_ld
        self.op_st : TraceEntry = op_st
        self.src_addr = None  # this is the virtual address
        self.dst_addr = None  # this is the virtual address
        self.size = None

        self.__init_vars()
        self.__init_type(pm_addr, pm_size)
        self.__sync_data_type()

    def __str__(self) -> str:
        return "%s(%s, %s, %d, %d)" % (self.type, hex(self.src_addr), hex(self.dst_addr), self.size, self.op_st.seq)

    def __repr__(self) -> str:
        return self.__str__()

    def __init_vars(self):
        self.src_addr = self.op_ld.addr
        self.dst_addr = self.op_st.addr
        self.size = self.op_ld.size

    def __init_type(self, pm_addr, pm_size):
        src_pm_addr = is_pm_addr(self.src_addr, pm_addr, pm_size)
        dst_pm_addr = is_pm_addr(self.dst_addr, pm_addr, pm_size)
        src_kn_addr = isKernelSpaceAddr(self.src_addr)
        dst_kn_addr = isKernelSpaceAddr(self.dst_addr)
        if src_pm_addr and dst_pm_addr:
            self.type = MemcpyType.PM_TO_PM
        elif src_pm_addr and dst_kn_addr:
            self.type = MemcpyType.PM_TO_KERNEL
        elif src_pm_addr and not dst_kn_addr:
            self.type = MemcpyType.PM_TO_USER
        elif src_kn_addr and dst_pm_addr:
            self.type = MemcpyType.KERNEL_TO_PM
        elif src_kn_addr and dst_kn_addr:
            self.type = MemcpyType.KERNEL_TO_KERNEL
        elif src_kn_addr and not dst_kn_addr:
            self.type = MemcpyType.KERNEL_TO_USER
        elif not src_kn_addr and dst_pm_addr:
            self.type = MemcpyType.USER_TO_PM
        elif not src_kn_addr and dst_kn_addr:
            self.type = MemcpyType.USER_TO_KERNEL
        else:
            self.type = MemcpyType.USER_TO_USER

    def __sync_data_type(self):
        if self.op_ld.stinfo_match and not self.op_st.stinfo_match:
            self.op_st.stinfo_match = self.op_ld.stinfo_match
            self.op_st.var_list = self.op_ld.var_list
        elif not self.op_ld.stinfo_match and self.op_st.stinfo_match:
            self.op_ld.stinfo_match = self.op_st.stinfo_match
            self.op_ld.var_list = self.op_st.var_list

    def dbg_get_detail(self):
        data = f'type: {self.type}, src: 0x{self.src_addr:x}, dst: 0x{self.dst_addr:x}, size: {self.size}, data type: {str(self.op_ld.stinfo_match)}\n'
        data += str(self.op_ld) + "\n"
        data += str(self.op_st)
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
