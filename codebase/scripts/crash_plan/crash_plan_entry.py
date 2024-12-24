import os
import sys
import time

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from scripts.crash_plan.crash_plan_type import CrashPlanType, CrashPlanSamplingType
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.cp_entry.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class CrashPlanEntry:
    '''
    Used to represent a crash plan and how to construct a crash image.
    Should be used with save_value trace.
    We use a list to store sequences, since the number of seq is small ( < 100)
    '''
    def __init__(self,
                 ty : CrashPlanType,
                 instruction_id,
                 start_seq,
                 persist_seqs : set,
                 exp_data_seqs : set,
                 info : str,
                 sampling_type : CrashPlanSamplingType = CrashPlanSamplingType.SamplingNone) -> None:
        self.type = ty
        # the instruction id of the investigated trace
        self.instruction_id : int = instruction_id
        # operations before this sequence should be all persisted
        # start sequence is not included to persist
        self.start_seq : int = start_seq
        # a set of sequence need to persist
        self.persist_seqs : set = persist_seqs
        # a set of sequence that need to check the data after recovery
        # if the recovered state matches the pre-consistent state, expect old data
        # if the recovered state matches the post-consistent state, expect new data
        self.exp_data_seqs : set = exp_data_seqs
        # the identity information for result
        self.info = info
        # the sampling type for memset, memory copies.
        self.sampling_type = sampling_type
        self.sampling_seq = None
        self.sampling_addr = None
        # Indicates how many CP entries this entry could represent.
        # If the number is 1, it represents itself.
        # If the number is larger than 1, it just represents the number of phoney CPs, and this instance cannot be used to generate crash image.
        self.num_cp_entries = 1

    def __str__(self) -> str:
        data = ""
        data += "type: %s\n" % (str(self.type))
        data += "inst id: %d\n" % (self.instruction_id)
        data += "start seq: %s\n" % (str(self.start_seq))
        data += "persist seqs: %s\n" % (str(sorted(list(self.persist_seqs))))
        data += "expected data seqs: %s\n" % (str(self.exp_data_seqs))
        data += "number of cps: %d\n" % (self.num_cp_entries)
        data += "info: %s" % (self.info)
        if self.sampling_addr:
            data += "sampling_type: %s, sampling_seq: %s, sampling_addr: %s" \
                % (str(self.sampling_type), str(self.sampling_seq), hex(self.sampling_addr))
        return data

    def __repr__(self) -> str:
        return self.__str__()

    def __member(self) -> tuple:
        if not self.sampling_addr and not self.sampling_seq:
            return (self.start_seq, self.persist_seqs, self.exp_data_seqs)
            # return (self.instruction_id, self.start_seq, self.persist_seqs, self.exp_data_seqs)
        else:
            return (self.start_seq, self.persist_seqs, self.exp_data_seqs, self.sampling_seq, self.sampling_addr)
            # return (self.instruction_id, self.start_seq, self.persist_seqs, self.exp_data_seqs, self.sampling_seq, self.sampling_addr)

    def __eq__(self, other) -> bool:
        if not isinstance(other, CrashPlanEntry):
            return False
        return self.__member() == other.__member()

    def __hash__(self) -> int:
        return hash(self.__member())
