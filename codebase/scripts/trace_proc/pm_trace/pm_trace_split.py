"""
PM trace split is used to split PM trace from all trace entries.

Only PM related trace will return, including:
1. load
2. store
3. NT store
4. asm
5. memtransfer/memset
6. flush
7. fence
"""

import os
import sys

scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(scripts_dir)

from trace_proc.trace_reader.trace_type import TraceType
from trace_proc.trace_reader.trace_entry import TraceEntry
from utils.logger import global_logger

def is_pm_addr(addr, pm_addr, pm_size) -> bool:
    return pm_addr <= addr <= pm_addr + pm_size

def is_pm_entry(entry : TraceEntry, pm_addr, pm_size) -> bool:
    if entry.type.isFlushTy() or entry.type.isFenceTy() or entry.type.isImpFenceTy():
        return True
    if entry.type.isStoreSeries() or entry.type.isLoadSeries():
        if pm_addr <= entry.addr and entry.addr + entry.size <= pm_addr + pm_size:
            return True
    return False
    # return entry.type.isFlushTy() or entry.type.isFenceTy() or entry.type.isImpFenceTy() or \
    #        (entry.type.isPMRelatedTy() and \
    #         pm_addr <= entry.addr and \
    #         entry.addr + entry.size <= pm_addr + pm_size)

def pm_split_seq_entrylist_map(seq_entry_list_map : dict, pm_addr, pm_size) -> dict:
    '''
    Input a dict(seq, entry_list), return a dict(seq, entry_list)
    '''
    rst = dict()

    # dbg_msg = "pm_split_seq_entrylist_map: pm addr and pm size: [0x%x, 0x%x]" % (pm_addr, pm_addr + pm_size)
    # global_logger.debug(dbg_msg)
    for seq, entry_list in seq_entry_list_map.items():
        if is_pm_entry(entry_list[0], pm_addr, pm_size):
            rst[seq] = entry_list
            # dbg_msg = "pm_split_seq_entrylist_map: %s is pm entry" % (str(entry_list[0]))
            # global_logger.debug(dbg_msg)
        # else:
        #     dbg_msg = "pm_split_seq_entrylist_map: %s is not pm entry" % (str(entry_list[0]))
        #     global_logger.debug(dbg_msg)
    
    global_logger.info("%d entry_list, %d pm entry_list" % (len(seq_entry_list_map), len(rst)))
    return rst
    
def pm_split_entrylist(entry_list : list, pm_addr, pm_size) -> list:
    '''
    Input a list(entry), return a list(entry)
    '''
    return [x for x in entry_list if is_pm_entry(x, pm_addr, pm_size)]
