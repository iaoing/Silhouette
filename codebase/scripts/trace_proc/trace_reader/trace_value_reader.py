import os
import sys
import binascii

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger, time_logger

class TraceValueEntry:
    """docstring for TraceValueEntry."""
    # this number is hard-coded in the Kernel tracing .c file
    OLD_VALUE_SEQ_BASE = 1000000000000

    def __init__(self, seq, data, size):
        self.seq  : int   = seq
        self.size : int   = size
        self.data : bytes = data

    def data_eq(self, other) -> bool:
        if not isinstance(other, TraceValueEntry):
            return False
        else:
            return self.size == other.size and self.data == other.data

    def valid(self) -> bool:
        if self.seq <= 0 or self.data == "" or self.size == 0:
            return False
        else:
            return True

    def to_int(self):
        if self.size <= 8:
            return int.from_bytes(self.data, byteorder='little', signed=False)
        return str(self.data)

    def to_str_full(self, max_bytes_print=8) -> str:
        if self.size > max_bytes_print:
            return f'{self.seq},{self.size},{binascii.hexlify(self.data[:8], " ").decode("ascii")} ...'
        else:
            return f'{self.seq},{self.size},{binascii.hexlify(self.data, " ").decode("ascii")}'

    def __str__(self):
        return self.to_str_full()

    @classmethod
    def is_old_value_seq(cls, seq):
        if seq >= cls.OLD_VALUE_SEQ_BASE:
            # cls.OLD_VALUE_SEQ_BASE refer OLDSV_START_SEQ in KernelTracing.c
            return True
        else:
            return False

    @classmethod
    def conv_to_trace_seq(cls, seq):
        if cls.is_old_value_seq(seq):
            return seq - cls.OLD_VALUE_SEQ_BASE
        else:
            return seq

class TraceValueReader:
    """Load trace vlaue file."""
    def __init__(self, fname = None):
        # seq : entry
        self.ov_map = dict()
        self.sv_map = dict()
        if fname != None:
            self.read_from_file(fname)

    def read_from_file(self, fname):
        cnt_ov = 0
        cnt_sv = 0
        fd = open(fname, 'rb')
        while True:
            seq_data = fd.read(8)

            if not seq_data:
                # reach EOF
                break

            if len(seq_data) != 8:
                log_msg = f'incorrect seq data length {len(seq_data)}'
                global_logger.critical(log_msg)
                assert False, log_msg

            size_data = fd.read(8)
            if not size_data or len(size_data) != 8:
                log_msg = f'incorrect size data length {len(size_data)}'
                global_logger.critical(log_msg)
                assert False, log_msg

            seq = int.from_bytes(seq_data, byteorder='little', signed=False)
            size = int.from_bytes(size_data, byteorder='little', signed=False)
            data = fd.read(size)

            if TraceValueEntry.is_old_value_seq(seq):
                seq = TraceValueEntry.conv_to_trace_seq(seq)
                if seq in self.ov_map:
                    log_msg = f'seq {seq} is already in the ov map'
                    global_logger.critical(log_msg)
                    assert False, log_msg
                else:
                    cnt_ov += 1
                    self.ov_map[seq] = TraceValueEntry(seq, data, size)
            else:
                if seq in self.sv_map:
                    log_msg = f'seq {seq} is already in the sv map'
                    global_logger.critical(log_msg)
                    assert False, log_msg
                else:
                    cnt_sv += 1
                    self.sv_map[seq] = TraceValueEntry(seq, data, size)

        fd.close()
        global_logger.debug("add %d ov, add %s sv from %s" % (cnt_ov, cnt_sv, fname))

    def clear(self):
        self.ov_map.clear()
        self.sv_map.clear()

