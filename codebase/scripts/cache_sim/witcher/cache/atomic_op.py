"""
Store, Flush, Fence operations in this file are not atomic operations.
"""
import os
import sys
from enum import Enum

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.cache_sim.witcher.misc.utils import Rangeable
from scripts.utils.logger import global_logger

class Flush(Rangeable):
    def __init__(self, seq, addr, size) -> None:
        self.seq = seq
        self.addr = addr
        self.size = size

    def __str__(self):
        return "Flush, seq %d, addr %d %s, size %d" % \
            (self.seq, self.addr, hex(self.addr), self.size)

    def __repr__(self) -> str:
        return self.__str__()

    def get_base_address(self):
        return self.addr

    def get_max_address(self):
        return self.addr + self.size

class Fence:
    def __init__(self, seq) -> None:
        self.seq = seq

    def __str__(self):
        return "Fence, seq %d" % (self.seq)

    def __repr__(self) -> str:
        return self.__str__()


class AtomicStoreState(Enum):
    VOLATILE  = 1
    FLUSHED   = 2
    PERSISTED = 3

class Store(Rangeable):
    def __init__(self, seq, addr, size) -> None:
        self.seq = seq
        self.addr = addr
        self.size = size
        # the state of this store
        self.state = AtomicStoreState.VOLATILE
        # a list of flush ops that flush this store
        self.flush_list = []
        # a list of fence ops that flush this store
        self.fence_list = []

    def __str__(self):
        return "Store, seq %d, addr %s, size %d" % \
            (self.seq, hex(self.addr), self.size)

    def __repr__(self) -> str:
        return self.__str__()

    def get_base_address(self):
        return self.addr

    def get_max_address(self):
        return self.addr + self.size

    def accept_flush(self, flush_op):
        assert isinstance(flush_op, Flush), "invalid flush op type: %s" % (type(flush_op))

        self.flush_list.append(flush_op)
        if self.is_flushing():
            global_logger.warning("duplicated flush: " + str(self))
        self.state = AtomicStoreState.FLUSHED

    def accept_fence(self, fence_op):
        assert isinstance(fence_op, Fence), "invalid fence op type: %s" % (type(fence_op))

        self.fence_list.append(fence_op)
        if self.is_clear():
            global_logger.warning("missing flush: " + str(self))
        else:
            self.state = AtomicStoreState.PERSISTED

    # check it is clear
    def is_clear(self):
        return self.state == AtomicStoreState.VOLATILE

    # check it is flushing
    def is_flushing(self):
        return self.state == AtomicStoreState.FLUSHED

    # check it is guaranteed to be persisted
    def is_presisted(self):
        return self.state == AtomicStoreState.PERSISTED

    def is_fenced_but_not_flushed(self):
        return len(self.flush_list) == 0 and len(self.fence_list) > 0
