import os
import sys
import logging

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.utils.logger import setup_global_logger
from scripts.utils.logger import global_logger

def main(argc, argv):
    if not (argc == 3 or argc == 4):
        assert False, ("invalid arguments.")

    setup_global_logger(fname="xx.log", file_lv=logging.DEBUG, stm=sys.stderr)

    stinfo_reader = StructInfoReader(argv[1])
    print(stinfo_reader.dbg_detail_info())

    trace_reader = TraceReader(argv[2])
    print(trace_reader)

    value_reader = None
    if argc == 4:
        value_reader = TraceValueReader(argv[3])
        trace_reader.merge_value_entries(value_reader)

    stinfo_index = StInfoIndex(trace_reader, stinfo_reader)

if __name__ == "__main__":
    argc = len(sys.argv)
    argv = sys.argv
    main(argc, argv)
