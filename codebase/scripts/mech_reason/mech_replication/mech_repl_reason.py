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
from scripts.trace_proc.trace_stinfo.addr_to_stinfo_entry import AddrToStInfoEntry
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_addr
from scripts.mech_reason.mech_memcpy.mech_memcpy_entry import MechMemcpyEntry, MemcpyType
from scripts.mech_reason.mech_memcpy.mech_memcpy_reason import MechMemcpyReason
from scripts.mech_reason.mech_store.mech_pmstore_entry import MechPMStoreEntry
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason, MechPMStoreEntry
from scripts.mech_reason.mech_replication.mech_repl_entry import MechReplEntry
from scripts.cheat_sheet.base.cheat_base import RepCheatSheetBase
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.mech_rep.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class MechReplReason:
    '''
    Current, only support replications if they are sync-ed by memcpy.
    '''
    def __init__(self, op_entry : OpTraceEntry,
                 pmstore_reason : MechPMStoreReason,
                 memcpy_reason : MechMemcpyReason,
                 sheet : RepCheatSheetBase) -> None:
        # a list of MechReplEntry
        self.entry_list = []
        self.sheet : RepCheatSheetBase = sheet

        self.__init_entries(op_entry, pmstore_reason, memcpy_reason)
        self.__init_mech_id()

    @timeit
    def __init_entries(self, op_entry : OpTraceEntry, pmstore_reason : MechPMStoreReason, memcpy_reason : MechMemcpyReason):
        # 1. find all memcpy to PM and the data type matches the cheat sheet
        candidate_iv_tree = IntervalTree()
        for cpy in memcpy_reason.entry_list:
            cpy : MechMemcpyEntry
            if not cpy.op_st.stinfo_match:
                continue
            if cpy.op_st.stinfo_match.stinfo.struct_name not in self.sheet.struct_set:
                continue
            if cpy.type == MemcpyType.PM_TO_PM:
                last_var_offset = cpy.op_st.stinfo_match.stinfo.children[-1].offset_bytes
                if cpy.size > last_var_offset:
                    # the structure could be a various-length structure
                    # thus, the last variable size do not matter
                    # we only check any bytes of the last variable is copied
                    entry = MechReplEntry()
                    entry.store_op = cpy
                    entry.store_pmstore = pmstore_reason.get_entry_by_seq(cpy.op_st.seq)[0]
                    entry.load_op_list.append(cpy)
                    self.entry_list.append(entry)
            elif cpy.type == MemcpyType.KERNEL_TO_PM:
                msg = f"found kernel to pm memcpy: {cpy}, {cpy.op_st.stinfo_match}"
                log.global_logger.debug(msg)
                last_var_offset = cpy.op_st.stinfo_match.stinfo.children[-1].offset_bytes
                if cpy.size > last_var_offset:
                    # the structure could be a variable-length structure
                    # thus, the last variable size do not matter
                    # we only check any bytes of the last variable is copied
                    entry = MechReplEntry()
                    entry.store_op = cpy
                    entry.store_pmstore = pmstore_reason.get_entry_by_seq(cpy.op_st.seq)[0]
                    self.entry_list.append(entry)
                    # the src addr is the DRAM address
                    candidate_iv_tree[cpy.src_addr : cpy.src_addr + cpy.size] = entry

        if log.debug:
            msg = "replication candidates iv tree:\n"
            for iv in candidate_iv_tree:
                iv : Interval
                msg += f"[0x{iv.begin:x}, 0x{iv.end:x}): {iv.data}\n"
            log.global_logger.debug(msg)

        # 2. find all src cpy of the candidates
        for cpy in memcpy_reason.entry_list:
            cpy : MechMemcpyEntry
            if not cpy.op_st.stinfo_match:
                continue
            if cpy.op_st.stinfo_match.stinfo.struct_name not in self.sheet.struct_set:
                continue
            if cpy.type == MemcpyType.PM_TO_KERNEL:
                # the dst addr is the DRAM address
                for iv in candidate_iv_tree[cpy.dst_addr : cpy.dst_addr + cpy.size]:
                    iv : Interval
                    entry : MechReplEntry = iv.data
                    if cpy.op_st.seq < entry.store_op.op_st.seq:
                        entry.load_op_list.append(cpy)

        # 3. keep the nearest memcpy in load op list
        for entry in self.entry_list:
            entry : MechReplEntry
            if len(entry.load_op_list) == 0:
                continue
            entry.load_op_list.sort(key=lambda x : x.op_st.seq, reverse=True)
            dram_addr_set : set = set(range(entry.store_op.src_addr, entry.store_op.src_addr + entry.store_op.size))
            idx = 0
            while idx < len(entry.load_op_list):
                cpy_entry : MechMemcpyEntry = entry.load_op_list[idx]
                dram_addr_set -= set(range(cpy_entry.dst_addr, cpy_entry.dst_addr + cpy_entry.size))
                if len(dram_addr_set) == 0:
                    break
                idx += 1
            if idx < len(entry.load_op_list):
                entry.load_op_list = entry.load_op_list[:idx + 1]
            entry.load_op_list.sort(key=lambda x : x.op_st.seq)

        # 4. find all writes to the src of the primary replica
        self.entry_list.sort(key = lambda x : x.store_op.op_st.seq)
        visited_seq = set()
        for entry in self.entry_list:
            entry : MechReplEntry
            if len(entry.load_op_list) == 0:
                continue
            lower_addr = min([x.src_addr for x in entry.load_op_list])
            upper_addr = max([x.src_addr + x.size for x in entry.load_op_list])
            pmstore_list = pmstore_reason.get_entry_by_addr_seq_range(0, entry.store_op.op_ld.seq, lower_addr, upper_addr)

            if log.debug:
                msg = f"replication locate stores to primary: {0}, {entry.store_op.op_ld.seq}, 0x{lower_addr:x}, 0x{upper_addr:x}\n"
                msg += f"{str(pmstore_list)}"
                log.global_logger.debug(msg)

            for pmstore in pmstore_list:
                pmstore : MechPMStoreEntry
                if pmstore.op.seq not in visited_seq:
                    entry.stores_to_primary_replica.append(pmstore)
                    visited_seq.add(pmstore.op.seq)

            # sort stores by seq
            entry.stores_to_primary_replica.sort(key=lambda x: x.op.seq)

    def __init_mech_id(self):
        num = 0
        for entry in self.entry_list:
            num += 1
            entry.mech_id = num

    @timeit
    def invariant_check(self):
        rst_list = []
        for entry in self.entry_list:
            entry : MechReplEntry
            rst_list += entry.invariant_check()
            if len(rst_list) > 0:
                msg = f"Replication invariant check failed: {rst_list}\n{entry.dbg_get_detail()}"
                log.global_logger.warning(msg)
        return rst_list

    def dbg_get_detail(self):
        data = ""
        for entry in self.entry_list:
            entry : MechReplEntry
            data += "Replication %d\n" % (entry.mech_id)
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
