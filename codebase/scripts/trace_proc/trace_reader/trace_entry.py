import os
import sys
from copy import copy

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.trace_proc.instid_srcloc_reader.instid_src_loc_reader import InstIdSrcLocEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_stinfo.addr_to_stinfo_entry import AddrToStInfoEntry
from tools.scripts.struct_info_reader.struct_entry import StructMemberVar
from scripts.utils.logger import global_logger, time_logger
from scripts.utils.const_var import CACHELINE_BYTES
from scripts.utils import utils as my_utils


class TraceEntry:
    """ TraceEntry repersents one trace record. """

    def __init__(self, line):
        self.type   : TraceType = None
        self.seq    : int       = -1  # seq number
        self.pid    : int       = -1  # process id
        self.instid : int       = -1  # instruction numbering id
        self.addr   : int       = -1  # address
        self.size   : int       = -1  # size
        self.st_name: str       = ""  # struct name (for GEP record)
        self.fn_name: str       = ""  # function name of the record
        self.caller : str       = ""  # caller name (for call record)
        self.callee : str       = ""  # callee name (for call record)

        self.raw_line: str = line  # the raw line read from file

        self.ov_entry: TraceValueEntry = None  # old value entry
        self.sv_entry: TraceValueEntry = None  # new value entry

        self.src_entry: InstIdSrcLocEntry = None  # source location

        self.stinfo_list = []   # a list of a list AddrToStInfoEntry
        self.stinfo_match : AddrToStInfoEntry = None  # the best matched AddrToStInfoEntry
        self.var_list = [] # a list of StructMemberVar, if stinfo_match is not None, this is all matched variables of it

        self.call_path = [] # the calling path to this seq, a list of function name

        self.__parse_line(line)

        self.is_nt_store = False
        if self.type.isStoreAndFlushTy():
            self.is_nt_store = True

    @classmethod
    def is_valid_trace_line(cls, line):
        return ("id:" in line)

    @classmethod
    def is_pair_call_entry(cls, e1, e2):
        return ((e1.type == TraceType.kStartCall and e2.type == TraceType.kEndCall) or \
                (e1.type == TraceType.kEndCall and e2.type == TraceType.kStartCall)) and \
                e1.pid == e2.pid and e1.caller == e2.caller and e1.callee == e2.callee

    @classmethod
    def is_pair_func_entry(cls, e1, e2):
        return ((e1.type == TraceType.kStartFn and e2.type == TraceType.kEndFn) or \
                (e1.type == TraceType.kEndFn and e2.type == TraceType.kStartFn)) and \
                e1.pid == e2.pid and e1.fn_name == e2.fn_name and e1.addr == e2.addr

    def __str__(self) -> str:
        return self.raw_line.strip() + ", " + str(self.src_entry)

    def __repr__(self) -> str:
        return self.raw_line

    def __member(self) -> tuple:
        return (self.seq, self.type, self.addr, self.size)

    def to_result_str(self) -> str:
        data = 'seq: %d, instid: %s, struct: %s, vars: %s, src: %s, call path: %s' \
                % (self.seq, self.instid, str(self.stinfo_match), str(self.var_list),
                   str(self.src_entry), str(self.call_path))
        return data

    def member(self) -> tuple:
        return (self.seq, self.type, self.addr, self.size)

    def __eq__(self, other) -> bool:
        if not isinstance(other, TraceEntry):
            return False
        return self.__member() == other.__member()

    def __hash__(self) -> int:
        return hash(self.__member())

    def __parse_line(self, line):
        ''' The line must be valid. '''
        assert self.is_valid_trace_line(line), "Invalid line!"

        line  = line.replace(",", " ").replace(".", " ")
        line  = ' '.join(line.split())
        items = line.split(' ')

        self.seq = int(items[0])
        self.pid = int(items[1])
        self.instid  = int(items[4])

        self.type = TraceType(items[2])

        # different records have different format, process them one by one.
        if items[2] == "startFunc" or items[2] == "endFunc" or \
                items[2] == "startBB" or items[2] == "endBB":
            self.addr = int(items[6], 0)
            self.fn_name = items[8]
        elif items[2] == "startCall" or items[2] == "endCall":
            self.caller = items[6]
            self.callee = items[8]
        elif items[2] == "ukasm":
            self.caller = items[7]
        elif items[2] == "DRAMStructPtr" or items[2] == "PMStructPtr" or \
                items[2] == "UKStructPtr":
            self.st_name = items[6]
            self.addr = int(items[8], 0)
            self.size = int(items[12])
        elif items[2] == "dbgStore":
            self.st_name = items[6]
            self.addr = int(items[8], 0)
            self.size = int(items[10])
        elif items[2] == "asmmemsetnt" or \
                items[2] == "memset" or \
                items[2] == "store" or items[2] == "load" or \
                items[2] == "memtransStore" or items[2] == "memtransLoad" or \
                items[2] == "asmxchg" or items[2] == "xchg" or \
                items[2] == "rmw" or items[2] == "cas":
            self.addr = int(items[6], 0)
            self.size = int(items[8])
        elif items[2] == "asmFlush":
            self.addr = my_utils.alignToFloor(int(items[6], 0), CACHELINE_BYTES)
            self.size = CACHELINE_BYTES
            global_logger.debug("flush %s aligned to %s, size: %d" % (hex(int(items[6], 0)), hex(self.addr), self.size))
        elif items[2] == "asmFence" or items[2] == "impFence":
            pass
        elif items[2] == "uaccessStore" or items[2] == "uaccessNTStore":
            self.addr = int(items[8], 0)
            self.size = int(items[10])
        elif items[2] == "uaccessLoad" or items[2] == "uaccessNTLoad":
            self.addr = int(items[6], 0)
            self.size = int(items[10])
        elif items[2] == "select":
            pass
        elif items[2] == "DaxDevInfo":
            self.addr = int(items[5], 0)  # start address
            endaddr = int(items[6], 0)
            self.size = int(items[7]) * 1048576  # size in bytes
            assert self.addr + self.size == endaddr, "invalid PM start addr [%d], end addr [%d], and size [%d]" % (self.addr, endaddr, self.size)
        elif items[2] == "centflush":
            self.addr = int(items[6], 0)
            self.size = int(items[8])
        else:
            assert False, "unknown trace record type [%s]" % (line)

def get_entry_list_from_line(line) -> list:
    '''
    Used to parse the line and return a list of sanitized entries.
    The sanitization includes:
    1. Align the address of flush record to 64 bytes.
    2. Separate store and flush of NT records.

    Q: Why need a list?
    A: For NT-related instruction record, it stores data and flushes data.
       The data that already in the cache line will be force evicted.
       Thus, we construct a flush record after a NT store.
       In this way, we can just treat a non-temporal store as a temporal store
       that is followed by a flush.
       https://stackoverflow.com/questions/34501243/what-happens-with-a-non-temporal-store-if-the-data-is-already-in-cache
    '''
    entry = TraceEntry(line)
    entry_list = [entry]

    if entry.type.isStoreAndFlushTy() or entry.type.isCASTy():
        flush_entry = copy(entry)
        flush_entry.type = TraceType.kAsmFlush

        lo_addr = my_utils.alignToFloor(flush_entry.addr, CACHELINE_BYTES)
        hi_addr = my_utils.alignToCeil(flush_entry.addr + flush_entry.size - 1, CACHELINE_BYTES)
        flush_entry.addr = lo_addr
        flush_entry.size = hi_addr - lo_addr

        entry_list.append(flush_entry)

        log_msg = f'normalize nt record flush addr: {hex(entry.addr)} -> {hex(flush_entry.addr)}, size: {entry.size} -> {flush_entry.size}'
        global_logger.debug(log_msg)

    return entry_list
