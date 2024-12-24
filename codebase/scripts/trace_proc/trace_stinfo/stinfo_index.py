import os
import sys
import time
from intervaltree import Interval, IntervalTree

scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(scripts_dir)

from tools.scripts.struct_info_reader.struct_entry import StructInfo, StructMemberVar
from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_addr
from scripts.trace_proc.trace_stinfo.addr_to_stinfo_entry import AddrToStInfoEntry
from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.stinfo_index.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper


class StInfoIndex:
    PADDING_MIN_SIZE = 16
    def __init__(self, trace_reader : TraceReader, stinfo_reader : StructInfoReader) -> None:
        self.trace_reader = trace_reader
        self.stinfo_reader = stinfo_reader

        # use to record the min structure size
        self.min_st_size = sys.maxsize

        # the key is pid, the value is a interval tree
        self.pid_addr_to_stinfo_iv = dict()

        self.__init()
        self.__init_trace_entry_stinfo()

    @timeit
    def __init(self):
        def helper(pid, addr, size, st_name):
            if st_name in self.stinfo_reader.struct_dict:
                stinfo : StructInfo = self.stinfo_reader.struct_dict[st_name]
                if size != stinfo.size_bytes:
                    # if the struct info is generated in one kernel version,
                    # the trace is generated is generated in another kernel version,
                    # the size could be different.
                    # We trust the trace.
                    log_msg = "mismatched struct size, %s, %s" % \
                                (str(entry), stinfo._raw_line)
                    log.global_logger.warning(log_msg)

                    stinfo.size_bytes = size
                    stinfo.size_bits = size * 8

                addr_stinfo = AddrToStInfoEntry(addr, stinfo)
                self.pid_addr_to_stinfo_iv[pid][addr : addr + size] = set(addr_stinfo)
                self.min_st_size = min(self.min_st_size, addr_stinfo.stinfo.size_bytes)

                log_msg = f'{pid}: {st_name} add range [{hex(addr)}, {hex(addr+size)}] -> {addr_stinfo}'
                log.global_logger.debug(log_msg)

                # add member variables if it is a nested structure
                for var in stinfo.children:
                    helper(pid, addr + var.offset_bytes, size - var.offset_bytes, var.type_name)

        for pid, mp in self.trace_reader.pid_seq_entry_map.items():
            if pid not in self.pid_addr_to_stinfo_iv:
                self.pid_addr_to_stinfo_iv[pid] = IntervalTree()
            for seq, entry_list in mp.items():
                for entry in entry_list:
                    entry : TraceEntry

                    if entry.type.isStructInfoSeries():
                        st_name = entry.st_name
                        addr = entry.addr
                        size = entry.size

                        if not is_pm_addr(addr, self.trace_reader.pm_addr, self.trace_reader.pm_size):
                            continue

                        helper(pid, addr, size, st_name)

        # worst-case O(n^2*log n), best-case O(n*log n)
        log.global_logger.debug("start split overlaps")
        for pid, iv_tree in self.pid_addr_to_stinfo_iv.items():
            iv_tree.split_overlaps()
        log.global_logger.debug("end split overlaps")

        # Completes in O(n*log n)
        log.global_logger.debug("start merge equals")
        def data_reducer(s1, s2):
            return s1 | s2
        for pid, iv_tree in self.pid_addr_to_stinfo_iv.items():
            iv_tree.merge_equals(data_reducer)
        log.global_logger.debug("end merge equals")

        if log.debug:
            log_msg = "struct info index intervals: \n"
            log.global_logger.debug(log_msg)
            for pid, iv_tree in self.pid_addr_to_stinfo_iv.items():
                for iv in iv_tree:
                    log_msg = "%d: [%s, %s] %s" % (pid, hex(iv.begin), hex(iv.end), str(iv.data))
                    log.global_logger.debug(log_msg)

    @timeit
    def __init_trace_entry_stinfo(self):
        # mem transfer may does not have a matched structure due to the anonymous address
        # this issue will be solved when reasoning copy-related operations
        for pid, mp in self.trace_reader.pid_seq_entry_map.items():
            for seq, entry_list in mp.items():
                for entry in entry_list:
                    entry : TraceEntry

                    addr = entry.addr
                    if not (is_pm_addr(addr, self.trace_reader.pm_addr, self.trace_reader.pm_size) and \
                            (entry.type.isStoreSeries() or entry.type.isLoadSeries())):
                        continue

                    iv_set = self.pid_addr_to_stinfo_iv[pid][addr]
                    if len(iv_set) == 0:
                        # if no data type, e.g., PMFS's extent tree
                        log_msg = "no intervals match the point query, %s, %s" \
                                % (str(entry), str(iv_set))
                        log.global_logger.warning(log_msg)
                    elif len(iv_set) > 1:
                        # Is this should be okay? Length-vairable structure?
                        err_msg = "more than one intervals match the point query, %s, %s" \
                                % (str(entry), str(iv_set))
                        log.global_logger.warning(err_msg)
                    else:
                        stinfo_list = list(iv_set)[0].data
                        log_msg = f"{pid}: found struct info for op, {str(entry)}, {str(stinfo_list)}"
                        log.global_logger.debug(log_msg)

                        # filter out stinfo that cannot fully contain this entry
                        stinfo_list = [x for x in stinfo_list if x.contains(entry.addr, entry.addr + entry.size)]

                        # get the corresponding variables
                        stinfo_list = [[x, x.get_vars_by_iv(entry.addr, entry.addr + entry.size)] for x in stinfo_list]
                        last_stinfo_list = stinfo_list

                        if len(stinfo_list) > 1:
                            # find the one that close to the entry, and the member variable is smaller
                            stinfo_list.sort(key = lambda x : (entry.addr - x[0].addr, x[1][0].size_bytes))
                            stinfo_list = stinfo_list[:1]

                        if len(stinfo_list) == 1:
                            entry.stinfo_list = stinfo_list
                            entry.stinfo_match = stinfo_list[0][0]
                            entry.var_list = sorted(list(stinfo_list[0][1]), key = lambda x : x.offset_bytes)
                            log_msg = "found one matched struct info for entry, %s, %s, %s" % (str(entry), str(entry.stinfo_match), str(entry.stinfo_list))
                            log.global_logger.debug(log_msg)
                        else:
                            # elif len(stinfo_list) == 0:
                            entry.stinfo_list = last_stinfo_list
                            entry.stinfo_match = None
                            log_msg = "does not find matched struct info for entry, %s, %s, %s" % (str(entry), str(entry.stinfo_match), str(entry.stinfo_list))
                            log.global_logger.warning(log_msg)


    def point_query_iv(self, pid, addr) -> Interval:
        if pid not in self.pid_addr_to_stinfo_iv:
            return None
        iv_set = self.pid_addr_to_stinfo_iv[pid][addr]
        if len(iv_set) == 0:
            # if there is an operation 'memcpy(src, dst, size)' without
            # the struct cast of the dst address, the point query in
            # the intervaltree will return None.
            log_msg = "no intervals match the point query, %s, %s" \
                    % (hex(addr), str(iv_set))
            log.global_logger.warning(log_msg)
            return None
        elif len(iv_set) > 1:
            err_msg = "more than one intervals match the point query, %s, %s" \
                    % (hex(addr), str(iv_set))
            log.global_logger.error(err_msg)
            assert False, err_msg
        else:
            pass
        return list(iv_set)[0]
