import os
import sys
import logging
from copy import copy

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(base_dir)

from scripts.tools_proc.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.tools_proc.annot_reader.annot_reader import AnnotReader
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr
from scripts.utils.logger import setup_global_logger
from scripts.utils.logger import global_logger
from logic_reason.mech.mech_store.mech_pmstore_reason import MechPMStoreReason
from logic_reason.mech.mech_link.mech_link_reason import MechLinkReason

def main(argc, argv):
    if argc != 5:
        print("usage: exe trace_file sv_file func_file stinfo_file")
        assert False, ("invalid arguments.")

    trace_file = argv[1]
    sv_file = argv[2]
    func_file = argv[3]
    stinfo_file = argv[4]

    setup_global_logger(fname="xx.log", file_lv=logging.DEBUG, stm=sys.stderr)

    trace_reader = TraceReader(trace_file)
    value_reader = TraceValueReader(sv_file)
    trace_reader.merge_value_entries(value_reader)

    func_annot = AnnotReader(func_file)

    stinfo_reader = StructInfoReader(stinfo_file)
    global_logger.debug(stinfo_reader.dbg_detail_info())
    stinfo_index = StInfoIndex(trace_reader, stinfo_reader)

    split_op_mgr = SplitOpMgr(trace_reader, func_annot)

    for split_entry in split_op_mgr.op_entry_list:
        pmstore_reason = MechPMStoreReason(split_entry)
        link_reason = MechLinkReason(split_entry, pmstore_reason, stinfo_index)
        print(split_entry.op_name)
        link_reason.dbg_print_detail()


if __name__ == "__main__":
    argc = len(sys.argv)
    argv = sys.argv
    main(argc, argv)
