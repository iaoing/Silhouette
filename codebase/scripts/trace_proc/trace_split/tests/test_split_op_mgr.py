import os
import sys
import logging
from copy import copy

scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(scripts_dir)

from tools_proc.annot_reader.annot_reader import AnnotReader
from trace_proc.trace_reader.trace_reader import TraceReader
from trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from trace_proc.trace_split.split_op_mgr import SplitOpMgr
from utils.logger import setup_global_logger
from utils.logger import global_logger

def main(argc, argv):
    if argc != 4:
        assert False, ("invalid arguments.")

    trace_file = argv[1]
    sv_file = argv[2]
    func_file = argv[3]

    setup_global_logger(fname="xx.log", file_lv=logging.INFO, stm=sys.stderr)

    trace_reader = TraceReader(trace_file)
    value_reader = TraceValueReader(sv_file)
    func_annot = AnnotReader(func_file)

    trace_reader.merge_value_entries(value_reader)

    split_op_mgr = SplitOpMgr(trace_reader, func_annot)
    # split_op_mgr.debug_print_all()
    # split_op_mgr.debug_print_all_pm()
    split_op_mgr.debug_print_brief()


if __name__ == "__main__":
    argc = len(sys.argv)
    argv = sys.argv
    main(argc, argv)
