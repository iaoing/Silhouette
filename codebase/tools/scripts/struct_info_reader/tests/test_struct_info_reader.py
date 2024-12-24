import os
import sys
import logging
from copy import copy

scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(scripts_dir)

from tools_proc.struct_info_reader.struct_info_reader import StructInfoReader
from utils.logger import setup_global_logger
from utils.logger import global_logger

def main(argc, argv):
    if not (argc == 2):
        assert False, ("invalid arguments.")

    setup_global_logger(fname="xx.log", file_lv=logging.DEBUG, stm=sys.stderr)

    stinfo_reader = StructInfoReader(argv[1])
    print(stinfo_reader.dbg_detail_info())

if __name__ == "__main__":
    argc = len(sys.argv)
    argv = sys.argv
    main(argc, argv)
