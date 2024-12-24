import os
import sys
import logging
from copy import copy

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader

def main(argv):
    if not (len(argv) == 2):
        assert False, ("invalid arguments.")

    trace = TraceValueReader(argv[1])
    for seq, entry in trace.sv_map.items():
        print(entry.to_str_full())

if __name__ == "__main__":
    main(sys.argv)
