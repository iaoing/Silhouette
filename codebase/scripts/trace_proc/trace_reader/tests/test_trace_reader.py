import os
import sys
import logging
from copy import copy

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.instid_srcloc_reader.instid_src_loc_reader import InstIdSrcLocReader
from scripts.utils.logger import setup_global_logger
from scripts.utils.logger import global_logger

def main(argc, argv):
    if not (argc == 2 or argc == 3 or argc == 4):
        assert False, ("invalid arguments.")

    setup_global_logger(fname="xx.log", file_lv=logging.DEBUG, stm=sys.stderr)

    trace_func_file = argv[1]
    trace_reader = TraceReader(trace_func_file)
    print(trace_reader)

    value_reader = None
    if argc >= 3:
        trace_value_file = argv[2]
        value_reader = TraceValueReader(trace_value_file)
        print(value_reader)
        trace_reader.merge_value_entries(value_reader)

    inst_id_src_reader = None
    if argc >= 4:
        inst_id_src_map_file = argv[3]
        inst_id_src_reader = InstIdSrcLocReader(inst_id_src_map_file)
        print(inst_id_src_reader)
        trace_reader.merge_srcloc_entries(inst_id_src_reader)

    for pid, mp in trace_reader.pid_seq_entry_map.items():
        msg = f'#### {pid}'
        global_logger.debug(msg)
        for seq, elist in mp.items():
            msg = f'{str(elist[0])}, {trace_reader.seq_func_tree[seq]}'
            global_logger.debug(msg)

    for seq in trace_reader.pm_store_seq_list:
        msg = f'{seq}: {trace_reader.seq_entry_map[seq][0]}, {trace_reader.seq_entry_map[seq][0].call_path}'
        global_logger.debug(msg)

if __name__ == "__main__":
    argc = len(sys.argv)
    argv = sys.argv
    main(argc, argv)
