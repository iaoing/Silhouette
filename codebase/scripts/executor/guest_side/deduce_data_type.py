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
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr, OpTraceEntry
from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.utils.utils import getTimestamp, fileExists
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
import scripts.vm_comm.memcached_lock as mc_lock
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.crash_plan.crash_plan_scheme_base import CrashPlanSchemeBase
from scripts.crash_plan.crash_plan_scheme_2cp import CrashPlanScheme2CP
from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.deduce_struct.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

@timeit
def deduce_data_type(env : EnvBase, trace_reader : TraceReader):
    stinfo_reader = StructInfoReader(env.STRUCT_LAYOUT_FNAME())
    stinfo_index = StInfoIndex(trace_reader, stinfo_reader)
    return stinfo_index
