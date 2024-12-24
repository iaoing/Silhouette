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
from scripts.fs_conf.nova.env_nova import EnvNova
from scripts.fs_conf.pmfs.env_pmfs import EnvPmfs
from scripts.fs_conf.winefs.env_winefs import EnvWinefs
from scripts.fs_conf.base.module_default import ModuleDefault
from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr, OpTraceEntry
from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from scripts.utils.utils import getTimestamp, fileExists
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
import scripts.vm_comm.memcached_lock as mc_lock
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.dedup.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

@timeit
def load_trace(env : EnvBase) -> TraceReader:
    trace_reader = TraceReader(env.DUMP_TRACE_FUNC_FNAME())
    return trace_reader

@timeit
def split_trace_by_fs_op(env : EnvBase, trace_reader : TraceReader) -> SplitOpMgr:
    vfs_op_info = SrcInfoReader(env.INFO_POSIX_FN_FNAME())
    fs_op_mgr = SplitOpMgr(trace_reader, vfs_op_info)
    return fs_op_mgr

def fs_op_seq_id(op_trace : OpTraceEntry):
    '''
    Return a list of int.
    The sequence ID is based on PM-related instruction IDs, including store, memset, memcpy, cas, nt_store, flush, fence, etc.
    '''
    return op_trace.pm_op_id

def simple_hash(op_id):
    return hash(op_id)

def atomic_get_unique_case_count(memcached_client : CMPooledClient):
    key = 'unique_case_count'
    unique_case_count = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return unique_case_count

@timeit
def insert_unique_ops_to_memcached(basename : str, op_name_list : list, unique_op_indices : list, memcached_client : CMPooledClient):
    # thread-safe
    for idx in unique_op_indices:
        unique_case_count = atomic_get_unique_case_count(memcached_client)
        key = f'unique_fs_op.{unique_case_count}'
        value = [basename, op_name_list[:idx+1]]
        mc_wrapper.mc_set_wrapper(memcached_client, key, value)
    return True

@timeit
def deduplicate(memcached_client : CMPooledClient, fs_op_mgr : SplitOpMgr, basename):
    # track prefix and current ops
    op_name_list = [x.op_name for x in fs_op_mgr.op_entry_list]
    # the index to op_name_list to indicate which op is unique
    unique_op_indices = []

    for op_idx in range(len(fs_op_mgr.op_entry_list)):
        op_trace = fs_op_mgr.op_entry_list[op_idx]

        if len(op_trace.pm_sorted_store_seq) == 0:
            # no PM stores
            continue

        op_seq_id = fs_op_seq_id(op_trace)
        op_seq_id = tuple(op_seq_id)
        hash_value = simple_hash(op_seq_id)

        key = f'hash_{hash_value}'
        value = 1

        if mc_wrapper.mc_add_wrapper(memcached_client, key, value, noreply=False) == True:
            unique_op_indices.append(op_idx)
        else:
            # someone added it
            continue

    if len(unique_op_indices) > 0:
        insert_unique_ops_to_memcached(basename, op_name_list, unique_op_indices, memcached_client)

    return unique_op_indices
