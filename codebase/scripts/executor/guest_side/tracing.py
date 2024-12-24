import os
import sys
import time
import glob
import re
import traceback
from enum import Enum
from pymemcache.client.base import PooledClient as CMPooledClient

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.fs_conf.base.env_base import EnvBase
from scripts.fs_conf.base.module_default import ModuleDefault
from scripts.shell_wrap.shell_cl_state import ShellCLState
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot
from scripts.executor.guest_side.validate_image import get_syslog, clear_syslog
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.tracing.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class TracingRstType(Enum):
    """The types of validation result."""
    GOOD                 = 'good'

    # this may because of the workload or the file system
    RECURSION_ERROR    = 'recursion_error'
    OPENDIR_ERROR      = 'opendir_error'
    READDIR_ERROR      = 'readdir_error'
    STAT_ERROR         = 'stat_error'
    LSTAT_ERROR        = 'lstat_error'
    SYSLOG_ERROR       = 'syslog_error'
    UNMOUNT_FAILED_ERROR = 'unmount_failed_error'
    UNKNOWN_STAT_ERROR = 'unknown_stat_error'

    @classmethod
    def get_type(self, s : str):
        if not s:
            return TracingRstType.UNKNOWN_STAT_ERROR
        elif 'error: recursion too depth' in s:
            return TracingRstType.RECURSION_ERROR
        elif 'opendir error' in s:
            return TracingRstType.OPENDIR_ERROR
        elif 'readdir error' in s:
            return TracingRstType.READDIR_ERROR
        elif 'stat error' in s:
            return TracingRstType.STAT_ERROR
        elif 'lstat error' in s:
            return TracingRstType.LSTAT_ERROR
        elif 'syslog error' in s:
            return TracingRstType.SYSLOG_ERROR
        elif 'umount error' in s:
            return TracingRstType.UNMOUNT_FAILED_ERROR
        else:
            return TracingRstType.UNKNOWN_STAT_ERROR

def tracing_error_exist(memcached_client, tp: TracingRstType):
    # this is not thread-safe, but it does not matter.
    hash_key = f'tracing_error:{tp.value}'
    value = mc_wrapper.mc_get_wrapper(memcached_client, hash_key)
    return value != None

def tracing_error_insert(memcached_client, tp: TracingRstType):
    # this is not thread-safe, but it does not matter.
    hash_key = f'tracing_error:{tp.value}'
    mc_wrapper.mc_set_wrapper(memcached_client, hash_key, 1)

def _get_unique_count_by_incr(memcached_client, key):
    num = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return num

@timeit
def proc_tracing_result(tp: TracingRstType, memcached_client, exe_path, other_msg):
    existing_key = f"TracingRstType.{tp.value}.{other_msg}"
    existing_key = str(hash(existing_key))
    if mc_wrapper.mc_add_wrapper(memcached_client, existing_key, '1'):
        key = f'TracingRstType.{tp.value}.count'
        num = _get_unique_count_by_incr(memcached_client, key)

        key = f'TracingRstType.{tp.value}.{num}'
        value = [os.path.basename(exe_path), other_msg]
        mc_wrapper.mc_set_wrapper(memcached_client, key, value)

    msg = f"tracing failed: {tp.value} for case {os.path.basename(exe_path)}\n{other_msg}"
    log.global_logger.error(msg)

def atomic_get_failed_case_count(memcached_client : CMPooledClient):
    # atomically get the count
    key = 'failed_case_count'
    failed_case_count = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return failed_case_count

def atomic_get_failed_ctx_case_count(memcached_client : CMPooledClient):
    # atomically get the count
    key = 'failed_ctx_case_count'
    failed_ctx_case_count = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return failed_ctx_case_count

def atomic_get_failed_syslog_case_count(memcached_client : CMPooledClient):
    # atomically get the count
    key = 'failed_syslog_case_count'
    failed_syslog_case_count = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return failed_syslog_case_count

def atomic_get_failed_umount_case_count(memcached_client : CMPooledClient):
    # atomically get the count
    key = 'failed_umount_case_count'
    failed_umount_case_count = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return failed_umount_case_count

@timeit
def insert_failed_test_case_to_memcached(basename : str, memcached_client : CMPooledClient):
    # thread-safe
    failed_case_count = atomic_get_failed_case_count(memcached_client)
    key = f'failed_test_case.{failed_case_count}'
    mc_wrapper.mc_set_wrapper(memcached_client, key, basename)
    return True

@timeit
def insert_failed_ctx_test_case_to_memcached(basename : str, memcached_client : CMPooledClient):
    # thread-safe
    failed_ctx_case_count = atomic_get_failed_ctx_case_count(memcached_client)
    key = f'failed_ctx_test_case.{failed_ctx_case_count}'
    mc_wrapper.mc_set_wrapper(memcached_client, key, basename)
    return True

@timeit
def insert_failed_umount_test_case_to_memcached(basename : str, memcached_client : CMPooledClient):
    # thread-safe
    failed_umount_case_count = atomic_get_failed_umount_case_count(memcached_client)
    key = f'failed_umount_test_case.{failed_umount_case_count}'
    mc_wrapper.mc_set_wrapper(memcached_client, key, basename)
    return True

@timeit
def insert_failed_syslog_test_case_to_memcached(basename : str, memcached_client : CMPooledClient):
    # thread-safe
    failed_syslog_case_count = atomic_get_failed_syslog_case_count(memcached_client)
    key = f'failed_syslog_test_case.{failed_syslog_case_count}'
    mc_wrapper.mc_set_wrapper(memcached_client, key, basename)
    return True

@timeit
def check_syslog():
    ret, log_msg = get_syslog()
    if not ret:
        return TracingRstType.SYSLOG_ERROR, log_msg
    elif 'nova error' in log_msg or 'pmfs error' in log_msg or 'winefs error' in log_msg:
        return TracingRstType.SYSLOG_ERROR, log_msg
    return TracingRstType.GOOD, None

@timeit
def mount_fs(fs_module : ModuleDefault):
    if not fs_module.insert_module():
        msg = f'{traceback.format_exc()}\nInsert module failed!'
        log.global_logger.critical(msg)
        raise GuestExceptionToRestartVM(msg)

    if not fs_module.mount_fs():
        msg = f'{traceback.format_exc()}\nMount failed!'
        log.global_logger.critical(msg)
        raise GuestExceptionToRestartVM(msg)

@timeit
def unmount_fs(fs_module : ModuleDefault):
    if not fs_module.unmount_fs():
        msg = f'{traceback.format_exc()}\nUmount failed!'
        log.global_logger.critical(msg)
        ret, syslog = get_syslog()
        return 200, 'umount error:\n' + syslog

    if not fs_module.remove_module():
        msg = f'{traceback.format_exc()}\nRemove module failed!'
        log.global_logger.critical(msg)
        ret, syslog = get_syslog()
        return 200, 'umount error:\n' + syslog

    return 0, ''

@timeit
def run_exec_file(fpath : str, env : EnvBase, fs_state_store_dir : str) -> int:
    cmd = f'sudo {fpath} {env.MOD_MNT_POINT()} {env.PM_SIZE_MB()}'
    if fpath.endswith('.sh'):
        # for custom .sh workload
        cmd = f'sudo {fpath} {env.MOD_MNT_POINT()} {env.DUMP_DISK_CONTENT_EXE()}'

    if fs_state_store_dir != None and isinstance(fs_state_store_dir, str):
        cmd += f' {fs_state_store_dir}'
    cl_state : ShellCLState = shell_cl_local_run(cmd, ttl=10, crash_on_err=False)
    if cl_state.code != 0:
        # sometime this is not a bug since ace workload may generate test cases that break POSIX semantic, e.g., rename a dir as its child
        msg = f'execute binary file failed: {cl_state.msg()}'
        log.global_logger.error(msg)
        return cl_state.code, cl_state.stderr.decode('utf-8', errors='replace')
    return cl_state.code, cl_state.stderr.decode('utf-8', errors='replace')

@timeit
def read_last_oracle_raw(fs_state_store_dir : str):
    oracle_list = []
    fpath_list = []
    for fpath in glob.glob(f'{fs_state_store_dir}/oracle_*.txt'):
        fpath_list.append(fpath)

    def extract_first_int(fpath):
        basename = os.path.basename(fpath)
        match = re.search(r'\d+', basename)
        return int(match.group()) if match else 0
    fpath_list.sort(key=extract_first_int)

    if len(fpath_list) == 0:
        return None

    data = None
    with open(fpath, 'r') as fd:
        data = fd.read()
    return data

@timeit
def tracing(memcached_client, fs_module : ModuleDefault, env : EnvBase, exe_fpath : str, fs_state_store_dir : str) -> int:
    clear_syslog()

    fs_module.use_instrumented_ko()
    mount_fs(fs_module)

    ret_code, err_msg = run_exec_file(exe_fpath, env, fs_state_store_dir)
    if ret_code != 0:
        tp : TracingRstType = TracingRstType.get_type(err_msg)
        _, syslog = get_syslog()
        err_msg += syslog
        proc_tracing_result(tp, memcached_client, exe_fpath, err_msg)
        # umount to prepare for the next round of test
        unmount_fs(fs_module)
        return ret_code

    # check if have any sys errors
    tp, syslog = check_syslog()
    if tp != TracingRstType.GOOD:
        proc_tracing_result(tp, memcached_client, exe_fpath, syslog)
        insert_failed_syslog_test_case_to_memcached(sys.path.basename(exe_fpath), memcached_client)
        # Since such syslog errors may be tolerated, do not stop here.

    ret_code, err_msg = unmount_fs(fs_module)

    if ret_code != 0:
        tp : TracingRstType = TracingRstType.get_type(err_msg)
        _, syslog = get_syslog()
        err_msg += syslog
        proc_tracing_result(tp, memcached_client, exe_fpath, err_msg)

    return ret_code
