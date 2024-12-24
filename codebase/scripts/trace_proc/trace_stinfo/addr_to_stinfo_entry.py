import os
import sys
from intervaltree import Interval, IntervalTree

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from tools.scripts.struct_info_reader.struct_entry import StructInfo, StructMemberVar
from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.utils.logger import global_logger

class AddrToStInfoEntry:
    def __init__(self, addr, stinfo : StructInfo) -> None:
        # the key (struct header address), the virtual address
        self.addr = addr

        # the struct info
        self.stinfo : StructInfo = stinfo

        # the beginning addr of variables
        self.var_addr_set = set()

        # address interval to variable map
        self.addr_to_var_iv = IntervalTree()

        self.__init()

    def contains(self, begin, end) -> bool:
        return (self.addr <= begin and end <= self.addr + self.stinfo.size_bytes)

    def aligned_addr(self, addr) -> bool:
        '''return true if the addr is aligned to variable's addr'''
        return addr in self.var_addr_set

    def get_var_by_addr(self, addr) -> StructMemberVar:
        ivs = self.addr_to_var_iv[addr]
        if len(ivs) == 0:
            return None
        return list(ivs)[0].data

    def get_vars_by_iv(self, begin, end) -> list:
        '''return a list of StructMemberVar, sorted by offset'''
        rst = []
        ivs = self.addr_to_var_iv[begin:end]
        for iv in ivs:
            rst.append(iv.data)
        rst.sort(key = lambda x : x.offset_bytes)
        return rst

    def __init(self):
        addr = self.addr
        self.var_addr_set.add(addr)
        for var in self.stinfo.children:
            var : StructMemberVar

            self.var_addr_set.add(addr + var.offset_bytes)
            self.addr_to_var_iv[addr + var.offset_bytes : addr + var.offset_bytes + var.size_bytes] = var

    def __str__(self) -> str:
        return "[%s, %s, %s]" % (hex(self.addr), hex(self.addr + self.stinfo.size_bytes), str(self.stinfo.struct_name))

    def __repr__(self) -> str:
        return self.__str__()

    def __iter__(self):
        self._count = 0
        return self

    def __next__(self):
        self._count += 1
        if self._count > 1:
            raise StopIteration
        return self

    def __member(self) -> tuple:
        return (self.addr, self.stinfo)

    def __eq__(self, other) -> bool:
        if not isinstance(other, AddrToStInfoEntry):
            return False
        return self.__member() == other.__member()

    def __hash__(self) -> bool:
        return hash(self.__member())


