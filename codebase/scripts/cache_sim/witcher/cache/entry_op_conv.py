"""
Convert entry to atomic op
"""

import os
import sys
import random

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.cache_sim.witcher.cache.atomic_op import Store, Flush, Fence
from scripts.utils.logger import global_logger
import scripts.utils.logger as log
from scripts.utils.const_var import ATOMIC_WRITE_BYTES, CACHELINE_BYTES, ATOMIC_SAMPLING_NUMBER
from scripts.utils.utils import isUserSpaceAddr
import scripts.utils.utils as my_utils

def convert_entry(entry : TraceEntry) -> list:
    '''Require: entry must an PM entry'''
    lst = []
    seq = entry.seq
    if entry.type.isFenceTy():
        lst.append(Fence(seq))
    elif entry.type.isFlushTy():
        flush_lst = []
        lo_addr = entry.addr
        hi_addr = entry.addr + entry.size
        while lo_addr < hi_addr:
            if lo_addr // CACHELINE_BYTES == hi_addr // CACHELINE_BYTES:
                # if in the same cache-line
                flush_lst.append(Flush(seq, lo_addr, hi_addr - lo_addr))
                break
            elif lo_addr % CACHELINE_BYTES == 0:
                # if lo addr is cacheline aligned
                flush_lst.append(Flush(seq, lo_addr, CACHELINE_BYTES))
                lo_addr += CACHELINE_BYTES
            else:
                # if lo addr is not cacheline aligned
                flush_lst.append(Flush(seq, lo_addr, CACHELINE_BYTES - lo_addr % CACHELINE_BYTES))
                lo_addr += CACHELINE_BYTES - lo_addr % CACHELINE_BYTES

        if log.debug:
            log_msg = "flush op: %s\n" % (str(entry))
            for atomic_op in flush_lst:
                log_msg += "atomic op: %s\n" % (str(atomic_op))
            global_logger.debug(log_msg)

        lst += flush_lst

    elif entry.type.isLoadSeries():
        # we do not process load trace
        pass
    elif entry.type.isCASTy():
        # PMFS and WineFS use 16-bytes CAS, we did not check the atomic size for CAS
        # TODO: what if the value is not within a cache line?
        lst.append(Store(seq, entry.addr, entry.size))
    else:
        # store, memcpy, nt-store, etc.
        lo_addr = my_utils.alignToFloor(entry.addr, ATOMIC_WRITE_BYTES)
        hi_addr = entry.addr + entry.size
        for addr in range(lo_addr, hi_addr, ATOMIC_WRITE_BYTES):
            size = ATOMIC_WRITE_BYTES

            if addr < entry.addr:
                size = addr + 8 - entry.addr
                addr = entry.addr

            if addr + size > hi_addr:
                size = hi_addr - addr

            if not entry.sv_entry:
                log_msg = "entry does not have sv entry, %s" % (entry.__str__())
                global_logger.error(log_msg)
                assert False, log_msg

            lst.append(Store(seq, addr, size))

    return lst

def convert_entry_list(entry_list : list,
                       ignore_nonatomic_write : bool,
                       nonatomic_as_one : bool,
                       sampling_nonatomic_write : bool) -> list:
    lst = []
    for entry in entry_list:
        if entry.type.isMemTransStore() or entry.type.isMemset():
            if ignore_nonatomic_write:
                continue

            tmp = convert_entry(entry)
            if nonatomic_as_one:
                lst.append(tmp[0])
            elif sampling_nonatomic_write and len(tmp) > ATOMIC_SAMPLING_NUMBER:
                lst += random.sample(tmp, ATOMIC_SAMPLING_NUMBER)
            else:
                lst += tmp
        else:
            lst += convert_entry(entry)

    return lst

def convert_seq_entrylist_dict(seq_entrylist_dict : dict,
                               ignore_nonatomic_write : bool,
                               nonatomic_as_one : bool,
                               sampling_nonatomic_write : bool) -> list:
    lst = []

    for seq, entry_list in sorted(seq_entrylist_dict.items()):
        lst += convert_entry_list(entry_list, ignore_nonatomic_write, nonatomic_as_one, sampling_nonatomic_write)

    return lst
