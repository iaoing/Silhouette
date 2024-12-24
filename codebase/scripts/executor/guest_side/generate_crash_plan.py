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
from scripts.utils.utils import getTimestamp, fileExists
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
import scripts.vm_comm.memcached_lock as mc_lock
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.cheat_sheet.base.cheat_base import CheatSheetBase
from scripts.crash_plan.crash_plan_scheme_base import CrashPlanSchemeBase
from scripts.crash_plan.crash_plan_scheme_2cp import CrashPlanScheme2CP
from scripts.crash_plan.crash_plan_scheme_mech2cp import CrashPlanSchemeMech2CP
from scripts.crash_plan.crash_plan_scheme_mechcomb import CrashPlanSchemeMechComb
from scripts.crash_plan.crash_plan_scheme_comb import CrashPlanSchemeComb
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.executor.guest_side.deduce_mech import DeduceMech
from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.gen_cp.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

@timeit
def generate_crash_plans(trace_reader : TraceReader, stinfo_index : StInfoIndex, op_entry : OpTraceEntry, mech_deduce : DeduceMech, scheme : str, ignore_nonatomic_write : bool, nonatomic_as_one : bool, sampling_nonatomic_write : bool) -> CrashPlanSchemeBase:
    crash_plan_scheme = None
    if scheme.lower() == '2cp':
        crash_plan_scheme = CrashPlanScheme2CP(op_entry, mech_deduce)
        crash_plan_scheme.generate_crash_plans(ignore_nonatomic_write, nonatomic_as_one, sampling_nonatomic_write)
    elif scheme.lower() == 'comb':
        crash_plan_scheme = CrashPlanSchemeComb(op_entry)
        crash_plan_scheme.generate_crash_plans(ignore_nonatomic_write, nonatomic_as_one, sampling_nonatomic_write)
    elif scheme.lower() == 'mech2cp':
        crash_plan_scheme = CrashPlanSchemeMech2CP(trace_reader, stinfo_index, op_entry, mech_deduce)
        crash_plan_scheme.generate_crash_plans(ignore_nonatomic_write, nonatomic_as_one, sampling_nonatomic_write)
        # comment the below line if not debugging the information
        crash_plan_scheme.sending_details_to_mc(trace_reader, op_entry)
    elif scheme.lower() == 'mechcomb':
        crash_plan_scheme = CrashPlanSchemeMechComb(trace_reader, stinfo_index, op_entry, mech_deduce)
        crash_plan_scheme.generate_crash_plans(ignore_nonatomic_write, nonatomic_as_one, sampling_nonatomic_write)
        # comment the below line if not debugging the information
        crash_plan_scheme.sending_details_to_mc(trace_reader, op_entry)
    else:
        raise NotImplementedError(f"Not implemented: {scheme}")

    return crash_plan_scheme
