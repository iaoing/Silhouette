import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.cache_sim.witcher.cache.cache_base import CacheBase
from scripts.cache_sim.witcher.cache.cache_base import CachelineBase
from scripts.cache_sim.witcher.cache.atomic_op import Store, Flush, Fence
from scripts.utils.const_var import CACHELINE_BYTES
from scripts.utils.const_var import ATOMIC_WRITE_BYTES
from scripts.utils.utils import alignToFloor, alignToCeil
from scripts.utils.logger import global_logger

# A WitcherCacheline is a list of buckets
class WitcherCacheline(CachelineBase):
    def __init__(self, address, size, binary_file):
        self.address = address
        self.size = size
        self.binary_file = binary_file
        # a cacheline needs the store list to track store order
        self.stores_list = []
        # a list of dup flush ops
        self.dup_flush_list = []

    def is_empty(self):
        return len(self.stores_list) == 0

    def accept_store(self, store_op):
        assert(self.can_accept_store_op(store_op)), (hex(self.address), self.size, store_op)
        # Update the store_list
        self.stores_list.append(store_op)

    def accept_flush(self, flush_op : Flush):
        assert(self.can_accept_flush_op(flush_op)), (hex(self.address), self.size, flush_op)

        # Mark all stores as flushing
        for store_op in self.stores_list:
            store_op : Store
            if flush_op.addr <= store_op.addr and store_op.addr + store_op.size <= flush_op.addr + flush_op.size:
                store_op.accept_flush(flush_op)

    def accept_fence(self, fence_op):
        # do not remove persisted stores
        for store_op in self.stores_list:
            if len(store_op.flush_list) > 1:
                self.dup_flush_list.append(store_op.flush_list)
            store_op.accept_fence(fence_op)

    def write_back_all_flushing_stores(self):
        # Write all flushing stores in the cache to the file
        # then update the store list
        unflushed_stores = []

        for store_op in self.stores_list:
            if store_op.is_flushing():
                self.binary_file.do_store(store_op)
            else:
                unflushed_stores.append(store_op)

        # Update the store_list
        self.stores_list = unflushed_stores

    def write_back_all_persisted_stores(self):
        # Write all persisted stores in the cache to the file
        # then update the store list
        unpersisted_stores = []

        for store_op in self.stores_list:
            if store_op.is_presisted():
                self.binary_file.do_store(store_op)
            else:
                unpersisted_stores.append(store_op)

        # Update the store_list
        self.stores_list = unpersisted_stores

    def force_write_back_all_stores(self):
        # Write all stores in the cache to the file
        for store_op in self.force_write_back_all_stores:
            self.binary_file.do_store(store_op)

        # Clear the store_list
#
        return len(self.stores_list) == 0

    def can_accept_store_op(self, store_op):
        return self.address <= store_op.addr and \
               store_op.addr + store_op.size <= self.address + self.size

    def can_accept_flush_op(self, flush_op):
        return self.address <= flush_op.addr and \
               self.address + self.size >= flush_op.addr + flush_op.size

        # return self.address == flush_op.addr and \
        #        self.size == flush_op.size

# WitcherCache is a list of cacheline
class WitcherCache(CacheBase):
    def __init__(self, binary_file):
        # a dict of cachelines: key:addr, val:cacheline
        self.cacheline_dict = dict()
        # binary file for writing
        self.binary_file = binary_file
        # used to monitor the last op
        self.last_op = None
        # the list of dup fence ops
        self.dup_fence_list = []
        # the list of dup flush ops
        self.dup_flush_list = []

    def accept(self, op):
        # global_logger.debug("accepting op: " + str(op))
        if isinstance(op, Store):
            self.accept_store(op)
        elif isinstance(op, Flush):
            self.accept_flush(op)
        elif isinstance(op, Fence):
            self.accept_fence(op)
            if self.last_op and isinstance(self.last_op, Fence):
                self.dup_fence_list.append([self.last_op, op])
        else:
            assert False, "not supported op [%s]" % (type(op))

        self.last_op = op

    # accept_store
    # create or find the cacheline and let it accept the store
    def accept_store(self, store_op):
        cacheline = self.get_cacheline_from_address(store_op.addr)
        cacheline.accept_store(store_op)

    # accept_flush
    # create or find the cacheline and let it accept the flush
    def accept_flush(self, flush_op):
        cacheline = self.get_cacheline_from_address(flush_op.addr)
        return cacheline.accept_flush(flush_op)

    # accept_fence
    def accept_fence(self, fence_op):
        for cacheline in self.get_cachelines():
            cacheline.accept_fence(fence_op)
            self.__update_dup_flush_list(cacheline)

    def __update_dup_flush_list(self, cacheline : WitcherCacheline):
        self.dup_flush_list += cacheline.dup_flush_list
        cacheline.dup_flush_list = []

    def write_back_all_flushing_stores(self):
        empty_cachelines = []
        for cacheline in self.get_cachelines():
            cacheline.write_back_all_flushing_stores()
            if cacheline.is_empty():
                empty_cachelines.append(cacheline)
        for cacheline in empty_cachelines:
            del self.cacheline_dict[cacheline.address]

    def write_back_all_persisted_stores(self):
        empty_cachelines = []
        for cacheline in self.get_cachelines():
            cacheline.write_back_all_persisted_stores()
            if cacheline.is_empty():
                empty_cachelines.append(cacheline)
        for cacheline in empty_cachelines:
            del self.cacheline_dict[cacheline.address]

    def force_write_back_all_stores(self):
        for cacheline in self.get_cachelines():
            cacheline.force_write_back_all_stores()
        self.cacheline_dict = dict()

    def get_all_volatile_ops(self):
        # return a list of volatile stores.
        lst = []
        for cacheline in self.get_cachelines():
            for store_op in cacheline.stores_list:
                if store_op.is_clear():
                    lst.append(store_op)
        return lst

    def get_all_flushing_ops(self):
        # return a list of flushing stores.
        lst = []
        for cacheline in self.get_cachelines():
            for store_op in cacheline.stores_list:
                if store_op.is_flushing():
                    lst.append(store_op)
        return lst

    def get_all_persisted_ops(self):
        # return a list of persisted stores.
        lst = []
        for cacheline in self.get_cachelines():
            for store_op in cacheline.stores_list:
                if store_op.is_presisted():
                    lst.append(store_op)
        return lst

    def get_all_ops(self):
        # return a list of stores.
        lst = []
        for cacheline in self.get_cachelines():
            for store_op in cacheline.stores_list:
                lst.append(store_op)
        return lst

    def get_in_fight_ops(self):
        return self.get_all_volatile_ops() + self.get_all_flushing_ops()

    def get_in_fight_nums(self):
        return len(self.get_all_volatile_ops()) + len(self.get_all_flushing_ops())

    # get the corresponding cacheline from an address , create one if not having
    def get_cacheline_from_address(self, address):
        cacheline_address = alignToFloor(address, CACHELINE_BYTES)
        if cacheline_address not in self.cacheline_dict:
            cacheline = WitcherCacheline(cacheline_address,
                                         CACHELINE_BYTES,
                                         self.binary_file)
            self.cacheline_dict[cacheline_address] = cacheline
        return self.cacheline_dict[cacheline_address]

    def get_cachelines(self):
        return self.cacheline_dict.values()
