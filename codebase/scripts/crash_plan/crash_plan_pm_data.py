import os
import sys
import logging
import glob

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from scripts.tools_proc.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.tools_proc.annot_reader.annot_reader import AnnotReader
from scripts.trace_proc.trace_reader.trace_reader import TraceReader, TraceEntry
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from codebase.scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr
from logic_reason.mech.mech_undojnl.mech_undojnl_reason import MechUndoJnlEntry, MechUndoJnlReason
from logic_reason.mech.mech_store.mech_pmstore_reason import MechPMStoreReason
from logic_reason.mech.mech_store.mech_cirtical_pmstore_reason import MechCirticalPMStoreReason
from logic_reason.mech.mech_link.mech_link_reason import MechLinkEntry, MechLinkReason
from logic_reason.mech.mech_lsw.mech_lsw_reason import MechLSWEntry, MechLSWReason
from logic_reason.mech.mech_memcpy.mech_memcpy_reason import MechMemcpyEntry, MechMemcpyReason
from logic_reason.mech.mech_replication.mech_repl_reason import MechReplEntry, MechReplReason
from logic_reason.crash_plan.crash_plan_entry import CrashPlanEntry, CrashPlanType
from scripts.utils.logger import global_logger

class CrashPlanPMData:
    '''The pm data used to construct crash images'''
    def __init__(self, trace_reader : TraceReader, sv_reader : TraceValueReader) -> None:
        self.pm_addr = trace_reader.pm_addr
        self.pm_size = trace_reader.pm_size
        # all split entry's pm id tuples
        self.pm_id_set = set()
        # address inside ov/sv entry is the virtual address, need to be converted
        # to physical address when constructing image
        self.seq_to_ov_entry = dict()
        self.seq_to_sv_entry = dict()
        self.__init(trace_reader, sv_reader)

    def __init(self, trace_reader : TraceReader, sv_reader : TraceValueReader) -> None:
        for seq in trace_reader.pm_store_seq_list:
            entry : TraceEntry = trace_reader.seq_entry_map[seq][0]

            if not entry.sv_entry or not entry.ov_entry:
                err_msg = "no value entry for the trace entry: %s" % (str(entry))
                global_logger.error(err_msg)
                assert entry.sv_entry and entry.ov_entry, err_msg

            if seq in self.seq_to_ov_entry:
                err_msg = "seq already in the dict: %s"
                global_logger.error(err_msg)
                assert False, err_msg

            log_msg = "%d, %s, %d, %s, %s, %s, %s, %s" % (entry.seq, hex(entry.addr),
                                          entry.size,
                                          str(entry.stinfo_match),
                                          str(entry.var_list)[:16],
                                          str(entry.src_entry),
                                          entry.ov_entry.data[:8],
                                          entry.sv_entry.data[:8])
            global_logger.debug(log_msg)

            self.seq_to_ov_entry[seq] = [entry.addr, entry.ov_entry]
            self.seq_to_sv_entry[seq] = [entry.addr, entry.sv_entry]

    def add_pm_id_num_list(self, lst):
        self.pm_id_set.add(tuple(lst))

    def dbg_detail_str(self, limit_hex_length = 8) -> str:
        data = ''
        for seq, lst in self.seq_to_sv_entry.items():
            data += "seq: %d, %s, %d, %s\n" % (seq, hex(lst[0]), lst[1].size, lst[1].data[:limit_hex_length])
        return data

