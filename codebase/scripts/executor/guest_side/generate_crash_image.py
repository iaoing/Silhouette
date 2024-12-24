import os
import sys
import time
import traceback
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde
from pymemcache import MemcacheUnexpectedCloseError

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase
from scripts.fs_conf.base.module_default import ModuleDefault
from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.trace_proc.trace_reader.trace_reader import TraceReader, TraceEntry
from scripts.cache_sim.witcher.binary_file.binary_file import EmptyBinaryFile, MemBinaryFile
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr, OpTraceEntry
from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from scripts.utils.utils import getTimestamp, fileExists, alignToCeil, alignToFloor, isAlignedBy
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
import scripts.vm_comm.memcached_lock as mc_lock
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.utils.const_var import ATOMIC_WRITE_BYTES
from scripts.crash_plan.crash_plan_entry import CrashPlanEntry, CrashPlanSamplingType, CrashPlanType
from scripts.crash_plan.crash_plan_scheme_base import CrashPlanSchemeBase
from scripts.crash_plan.crash_plan_scheme_2cp import CrashPlanScheme2CP
from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.gen_img.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

@timeit
def put_trace_to_img(img : MemBinaryFile, trace_reader : TraceReader, start_seq, end_seq):
    '''
    Put trace from op_entry to the image file until the end of the seq.
    The start seq is included.
    The end seq is not included.
    '''
    count = 0
    for seq in trace_reader.pm_store_seq_list:
        if seq < start_seq:
            continue
        if seq >= end_seq:
            break

        op : TraceEntry = trace_reader.seq_entry_map[seq][0]
        if op.type.isStoreSeries() and op.sv_entry:
            count += 1
            img.do_store_direct(op.addr - trace_reader.pm_addr, op.addr + op.size - trace_reader.pm_addr, op.sv_entry.data)
        else:
            msg = f"The trace record is not store or does not have stored value: {op}, {op.sv_entry}"
            log.global_logger.error(msg)

    msg = f"stored {count} trace records out of {len(trace_reader.pm_store_seq_list)}"
    log.global_logger.debug(msg)

# @timeit
# do not timing it since the elapsed time is ~68 macroseconds, which is less than the time to send msg to the server (~140 macroseconds).
def put_op_trace_to_img(img : MemBinaryFile, op_entry : OpTraceEntry, start_seq, end_seq):
    '''
    Put trace from op_entry to the image file until the end of the seq.
    The start seq is included.
    The end seq is not included.
    '''
    count = 0
    for seq in op_entry.pm_sorted_store_seq:
        if seq < start_seq:
            continue
        if seq >= end_seq:
            break

        op : TraceEntry = op_entry.pm_seq_entry_map[seq][0]
        if op.type.isStoreSeries() and op.sv_entry:
            count += 1
            img.do_store_direct(op.addr - op_entry.pm_addr, op.addr + op.size - op_entry.pm_addr, op.sv_entry.data)
        else:
            msg = f"The trace record is not store or does not have stored value: {op}, {op.sv_entry}"
            log.global_logger.error(msg)

    msg = f"stored {count} trace records out of {len(op_entry.pm_sorted_store_seq)}"
    log.global_logger.debug(msg)

# @timeit
# do not timing it since the elapsed time is ~122 macroseconds, which is less than the time to send msg to the server (~140 macroseconds).
def put_cp_to_img(img : MemBinaryFile, op_entry : OpTraceEntry, cp : CrashPlanEntry) -> CrashPlanSchemeBase:
    for seq in op_entry.pm_sorted_store_seq:
        if seq < cp.start_seq:
            op : TraceEntry = op_entry.pm_seq_entry_map[seq][0]
            img.do_store_direct(op.addr - op_entry.pm_addr, op.addr + op.size - op_entry.pm_addr, op.sv_entry.data)

        elif cp.sampling_type != CrashPlanSamplingType.SamplingNone and seq == cp.sampling_seq:
            op : TraceEntry = op_entry.pm_seq_entry_map[seq][0]
            lower_addr = cp.sampling_addr
            if lower_addr < op.addr:
                lower_addr = op.addr
            upper_addr = cp.sampling_addr + ATOMIC_WRITE_BYTES
            if not isAlignedBy(upper_addr, ATOMIC_WRITE_BYTES):
                upper_addr = alignToFloor(upper_addr, ATOMIC_WRITE_BYTES)
            if upper_addr > op.addr + op.size or upper_addr < lower_addr:
                upper_addr = op.addr + op.size
            img.do_store_direct(lower_addr - op_entry.pm_addr, upper_addr - op_entry.pm_addr, op.sv_entry.data)

            msg = f"sampling data in image: [{lower_addr:#f}, {upper_addr:#f}); the op: [{op.addr:#f}, {op.addr + op.size:#f})"
            log.global_logger.debug(msg)

        elif seq in cp.persist_seqs:
            op : TraceEntry = op_entry.pm_seq_entry_map[seq][0]
            img.do_store_direct(op.addr - op_entry.pm_addr, op.addr + op.size - op_entry.pm_addr, op.sv_entry.data)
