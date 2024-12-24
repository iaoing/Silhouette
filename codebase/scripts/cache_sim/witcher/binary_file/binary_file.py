from __future__ import annotations
import io
import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

import scripts.cache_sim.witcher.misc.utils as wt_utils
from scripts.utils.logger import global_logger

class BinaryFile:

    def __init__(self, file_name, map_base : int, pmsize = 0):
        self.file_name = file_name
        self.map_base = map_base
        self.pmsize = pmsize

        self._file_map = wt_utils.memory_map(file_name)

    def __str__(self):
        return self.file_name

    # Write using a store op
    def do_store(self, store_op):
        base_off = store_op.get_base_address() - self.map_base
        max_off = store_op.get_max_address() - self.map_base
        self._file_map[base_off:max_off] = store_op.value_bytes
        # only flush before crash
        # self._file_map.flush(base_off & ~4095, 4096)

        # global_logger.debug(
        #          "file_name:%s, store_op:%s, base_off:%s, max_off:%s, value:%s",
        #          self.file_name, store_op.__str__(), hex(base_off), hex(max_off),
        #          store_op.value_bytes.hex())

    # write using base_off, max_off and val, this is used by PMDK Trace Handler
    def do_store_direct(self, base_off, max_off, val):
        self._file_map[base_off:max_off] = val
        # only flush before crash
        # self._file_map.flush(base_off & ~4095, 4096)

    # only flush before crash
    def flush(self):
        self._file_map.flush()


class EmptyBinaryFile:

    def __init__(self, file_name="", map_base : int = 0, pmsize = 0):
        self.file_name = file_name
        self.map_base = map_base
        self.pmsize = pmsize

    def __str__(self):
        return self.file_name

    # Write using a store op
    def do_store(self, store_op):
        pass

    # write using base_off, max_off and val, this is used by PMDK Trace Handler
    def do_store_direct(self, base_off, max_off, val):
        pass

    # only flush before crash
    def flush(self):
        pass


class MemBinaryFile:

    def __init__(self, file_name, map_base : int, pmsize):
        self.file_name = file_name
        self.map_base = map_base
        self.pmsize = pmsize  # in bytes

        initial_bytes = b'\x00' * pmsize
        self.memfd = io.BytesIO(initial_bytes)

    def __str__(self):
        return self.file_name

    # Write using a store op
    def do_store(self, store_op):
        base_off = store_op.get_base_address() - self.map_base
        max_off = store_op.get_max_address() - self.map_base

        self.memfd.seek(base_off)
        self.memfd.write(store_op.value_bytes)
        # only flush before crash
        # self._file_map.flush(base_off & ~4095, 4096)

        # global_logger.debug(
        #          "file_name:%s, store_op:%s, base_off:%s, max_off:%s, value:%s",
        #          self.file_name, store_op.__str__(), hex(base_off), hex(max_off),
        #          store_op.value_bytes.hex())

    def do_store_direct(self, base_off, max_off, val):
        assert base_off <= max_off, "invalid write range [%d - %d]" % (base_off, max_off)
        self.memfd.seek(base_off)
        self.memfd.write(val[:max_off - base_off])

        log_msg = "base_off: %s, size %d, val: %s" % (hex(base_off), max_off-base_off, val[:8])
        global_logger.debug(log_msg)
        # only flush before crash
        # self._file_map.flush(base_off & ~4095, 4096)

    def flush(self):
        self.memfd.flush()

    def copy(self, fname) -> MemBinaryFile:
        dup = MemBinaryFile(fname, self.map_base, self.pmsize)
        dup.memfd.seek(0)
        dup.memfd.write(self.memfd.getbuffer())
        return dup

    def dumpToFile(self, fname) -> int:
        # return the size of this file
        # assert self.file_name == fname, "mismatched file name %s and %s" % (self.file_name, fname)
        # check if the size of memfd is less than the pm size
        assert self.memfd.getbuffer().nbytes <= self.pmsize, "too larger memfd size %d than %d" \
            % (self.memfd.getbuffer().nbytes, self.pmsize)
        # write the current data to the specified file
        fd = open(fname, "wb")
        fd.truncate(self.pmsize)
        fd.seek(0)
        fd.write(self.memfd.getbuffer())

        fd.seek(0, os.SEEK_END)
        file_size = fd.tell()

        fd.close()
        return file_size

    def dumpToDev(self, dev_name):
        '''Required: sudo privilege'''
        fd = os.open(dev_name, os.O_RDWR)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, self.memfd.getbuffer())
        os.close(fd)
