import os
import sys
import time
from copy import copy
from intervaltree import Interval, IntervalTree

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.trace_proc.instid_srcloc_reader.instid_src_loc_reader import InstIdSrcLocEntry
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_addr
from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_entry import get_entry_list_from_line
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.instid_srcloc_reader.instid_src_loc_reader import InstIdSrcLocReader
from scripts.utils.logger import global_logger, time_logger
import scripts.utils.logger as log
from scripts.utils import utils as my_utils

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.trace_reader.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class TraceReader:
    """ Read trace records from a file. """
    def __init__(self, fname):
        self.fname = fname

        # the pm information got from the trace
        self.pm_addr = -1
        self.pm_size = -1

        # dict(seq, entry_list)
        self.seq_entry_map = dict()

        # seq to pid dict
        self.seq_to_pid_map = dict()

        # dict(pid, dict(seq, entry_list))
        self.pid_seq_entry_map = dict()

        # the seq range to function tree, e.g.,
        # [1, 100] : [fn1], [5, 20] : [fn1, fn2], [10, 15] : [fn1, fn2, fn3]
        # if a entry's seq in [10, 15], the call path is fn1 -> fn2 -> fn3
        # if a entry's seq in [1, 5], ths call path is fn1
        # pid -> Interval tree, which maps seq interval to function names
        self.pid_seq_func_tree = dict()

        self.__load_entries(fname)
        self.__match_functions()
        self.__set_call_path()

        # all pm store related seq
        self.pm_store_seq_list = []
        self.__init_pm_store_seq_list()

    @timeit
    def merge_value_entries(self, value_reader : TraceValueReader):
        for seq, entry_list in self.seq_entry_map.items():
            for entry in entry_list:
                entry : TraceEntry

                if entry.type != TraceType.kAsmFlush:
                    if entry.seq in value_reader.ov_map and entry.seq in value_reader.sv_map:
                        entry.ov_entry = value_reader.ov_map[entry.seq]
                        entry.sv_entry = value_reader.sv_map[entry.seq]
                    elif entry.seq in value_reader.ov_map or entry.seq in value_reader.sv_map:
                        log_msg = "seq [%d] only exist in ov or sv map!" % (entry.seq)
                        global_logger.error(log_msg)
                        assert False, log_msg

    @timeit
    def merge_srcloc_entries(self, loc_reader : InstIdSrcLocReader):
        for seq, elist in self.seq_entry_map.items():
            instruction_id = elist[0].instid
            if instruction_id in loc_reader.id_loc_map:
                for entry in elist:
                    entry.src_entry = loc_reader.id_loc_map[instruction_id]

    @timeit
    def __load_entries(self, fname):
        fd = open(fname, 'r')
        for line in fd:
            if TraceEntry.is_valid_trace_line(line):
                entry_list = get_entry_list_from_line(line)

                if len(entry_list) == 0:
                    log_msg = "parse entry failed from line [%s]" % (line)
                    global_logger.critical(log_msg)
                    assert False, log_msg
                elif entry_list[0].seq in self.seq_entry_map:
                    log_msg = "entry seq [%d] is aleardy in map, line [%s]" % (entry_list[0].seq, line)
                    global_logger.critical(log_msg)
                    assert False, log_msg
                else:
                    ty = entry_list[0].type
                    pid = entry_list[0].pid
                    seq = entry_list[0].seq

                    self.seq_entry_map[seq] = entry_list

                    if ty.isDaxDevTy():
                        self.pm_addr = entry_list[0].addr
                        self.pm_size = entry_list[0].size

                    if pid not in self.pid_seq_entry_map:
                        self.pid_seq_entry_map[pid] = dict()
                    if seq in self.pid_seq_entry_map[pid]:
                        log_msg = "entry seq [%d] is aleardy in map, line [%s]" % (entry_list[0].seq, line)
                        global_logger.critical(log_msg)
                        assert False, log_msg

                    self.seq_to_pid_map[seq] = pid
                    self.pid_seq_entry_map[pid][seq] = entry_list

        if not my_utils.isKernelSpaceAddr(self.pm_addr):
            log_msg = "invalid dax device information [%d, %d]" % (self.pm_addr, self.pm_size)
            global_logger.critical(log_msg)
            assert False, log_msg

        log_msg = "Load [%d] entries, [%d] pids, from [%s]" % \
                (len(self.seq_entry_map), len(self.pid_seq_entry_map), fname)
        global_logger.debug(log_msg)

    @timeit
    def __match_functions(self):
        '''
        The callee name of indirect calls (call through function pointer) does
        not match the real function name.
        This method is going to process call and function records to match names.

        For example, the pointer is open_ptr, the real function name is my_open,
        in the trace, the callee name of call_record is "open_ptr", but the
        function name of the corresponding function_record is "my_open".

        The sequence of records are:
        start_call -> start_func -> end_func -> end_call
        '''
        for pid, seq_map in self.pid_seq_entry_map.items():
            if pid not in self.pid_seq_func_tree:
                self.pid_seq_func_tree[pid] = IntervalTree()
            call_stack = []
            for seq, entry_list in sorted(seq_map.items()):
                entry = entry_list[0]
                entry : TraceEntry

                if entry.type == TraceType.kStartCall:
                    log_msg = f'start of call [{entry.callee}]'
                    global_logger.debug(log_msg)
                    call_stack.append(entry)
                elif entry.type == TraceType.kEndCall:
                    log_msg = f'end of call [{entry.callee}]'
                    global_logger.debug(log_msg)
                    if len(call_stack) == 0 or \
                            not TraceEntry.is_pair_call_entry(call_stack[-1], entry):
                        log_msg = "invalid pair of call entries:\n%s\n%s\n" % (call_stack[-1].__str__(), entry.__str__())
                        global_logger.critical(log_msg)
                        assert False, log_msg
                    else:
                        call_stack[-1].callee = call_stack[-1].fn_name
                        entry.callee = call_stack[-1].callee
                        # reset fn_name
                        call_stack[-1].fn_name = ""
                        # remove the last one
                        call_stack.pop(-1)
                elif entry.type == TraceType.kStartFn:
                    log_msg = f'start of func [{entry.fn_name}]'
                    global_logger.debug(log_msg)
                    if len(call_stack) > 0 and call_stack[-1].type == TraceType.kStartCall:
                        # call entry's fn_name is empty, use it as a temp store.
                        log_msg = f'change start call func name [{call_stack[-1].fn_name}] -> [{entry.fn_name}]'
                        global_logger.debug(log_msg)
                        call_stack[-1].fn_name = entry.fn_name
                    call_stack.append(entry)
                elif entry.type == TraceType.kEndFn:
                    log_msg = f'end of func [{entry.fn_name}]'
                    global_logger.debug(log_msg)
                    if len(call_stack) == 0 or \
                            not TraceEntry.is_pair_func_entry(call_stack[-1], entry):
                        log_msg = "invalid pair of function entries:\n%s\n%s\n" % (call_stack[-1].__str__(), entry.__str__())
                        global_logger.critical(log_msg)
                        assert False, log_msg
                    else:
                        log_msg = f'pair of end of func [{call_stack[-1].fn_name}]'
                        global_logger.debug(log_msg)
                        self.pid_seq_func_tree[pid][call_stack[-1].seq : entry.seq] = entry.fn_name
                        call_stack.pop(-1)
                else:
                    pass

            if len(call_stack) > 0:
                log_msg = "Remaining entries in call stack:\n"
                for call in call_stack:
                    log_msg += call.__str__().strip() + "\n"
                global_logger.warning(log_msg)

    @timeit
    def __set_call_path(self):
        for seq, elist in self.seq_entry_map.items():
            pid = elist[0].pid
            if pid in self.pid_seq_func_tree:
                for entry in elist:
                    entry.call_path = [iv.data for iv in sorted(self.pid_seq_func_tree[pid][seq])]

    @timeit
    def __init_pm_store_seq_list(self):
        for seq, lst in self.seq_entry_map.items():
            entry : TraceEntry = lst[0]
            if entry.type.isStoreSeries():
                if is_pm_addr(entry.addr, self.pm_addr, self.pm_size):
                    self.pm_store_seq_list.append(seq)
