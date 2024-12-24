'''
Example runs:
python3 ./main_guest.py --fs_type winefs --num_cases_to_test 1 --crash_plan_scheme mech2cp --dump_crash_plan_to_disk 1 --dump_disk_content_to_disk 1 --vm_id vm8001 --not_dedup 1 --keep_intermidiate_result 1 --stop_after_gen_crash_plan 1 --time_logger_local_file log.time --logging_file log.guest --logging_level 10
'''

import os
import sys
import argparse
from distutils.util import strtobool
import time
import traceback
import re
import glob
import copy
import random
import signal
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde
from pymemcache import MemcacheUnexpectedCloseError

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase
from scripts.fs_conf.base.env_phoney import EnvPhoney
from scripts.fs_conf.nova.env_nova import EnvNova
from scripts.fs_conf.pmfs.env_pmfs import EnvPmfs
from scripts.fs_conf.winefs.env_winefs import EnvWinefs
from scripts.fs_conf.base.module_default import ModuleDefault
from scripts.cache_sim.witcher.binary_file.binary_file import EmptyBinaryFile, MemBinaryFile
from scripts.cache_sim.witcher.cache.witcher_cache import WitcherCache
from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr, OpTraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.instid_srcloc_reader.instid_src_loc_reader import InstIdSrcLocReader
from tools.scripts.src_info_reader.src_info_reader import SrcInfoReader
from tools.scripts.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.utils.utils import getTimestamp, fileExists, mkdirDirs, removeDir
from tools.scripts.disk_content.ctx_file_reader import CtxFileReader, DiskEntryAttrs
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
import scripts.vm_comm.memcached_lock as mc_lock
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.vm_mgr.guest_state import GuestState
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.vm_mgr.guest_exception_handler import handle_uncaught_exception
from scripts.vm_mgr.guest_signal_handler import signal_handler
from scripts.cheat_sheet.base.cheat_base import CheatSheetBase
from scripts.cheat_sheet.nova.cheat_nova import CheatSheetNova
from scripts.cheat_sheet.pmfs.cheat_pmfs import CheatSheetPMFS
from scripts.cheat_sheet.winefs.cheat_winefs import CheatSheetWineFS
from scripts.utils.exceptions import GuestExceptionToRestoreSnapshot, GuestExceptionForDebug, GuestExceptionToRestartVM
import scripts.executor.guest_side.tracing as tracing
import scripts.executor.guest_side.dedup as dedup
from scripts.crash_plan.crash_plan_entry import CrashPlanEntry
from scripts.executor.guest_side.deduce_mech import DeduceMech
import scripts.executor.guest_side.deduce_data_type as deducedatatype
import scripts.executor.guest_side.generate_crash_plan as crashplan
import scripts.executor.guest_side.generate_crash_image as crashimage
import scripts.executor.guest_side.validate_image as validator
import scripts.utils.logger as log

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--fs_type", type=str,
                        required=True,
                        help="NOVA/PMFS/WineFS.")
    parser.add_argument("--num_cases_to_test", type=int,
                        required=False, default=sys.maxsize,
                        help="The number of test cases to run. Unlimited in default.")
    parser.add_argument("--test_case_basename", type=str,
                        required=False, default=None,
                        help="Specifically run this test case before others in test_case_dir. Note that this argument is different from the one in the host script")
    parser.add_argument("--shuffle_test_cases", type=lambda x: bool(strtobool(x)),
                        required=False, default=True,
                        help="Shuffle test cases.")
    parser.add_argument("--shuffle_seed", type=int,
                        required=False, default=0x1234abcd,
                        help="The seed for randomly shuffle test cases.")
    parser.add_argument("--crash_plan_scheme", type=str,
                        required=True,
                        choices=['2cp', 'comb', 'mech2cp', 'mechcomb'],
                        help="The scheme to generate crash plans.")
    parser.add_argument("--dump_crash_plan_to_disk", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the generated crash plans will be written to disk.")
    parser.add_argument("--dump_crash_image_to_disk", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the generated crash image will be written to disk. NB, if the image size is big, the disk space will be depleted quickly.")
    parser.add_argument("--dump_disk_content_to_disk", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the disk content will be written to disk.")
    parser.add_argument("--vm_id", type=str,
                        required=True,
                        help="The VM ID for distinguishing.")
    parser.add_argument("--not_dedup", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the deduplication process will not be performed.")
    parser.add_argument("--not_dedup_test_last", type=lambda x: bool(strtobool(x)),
                        required=False, default=True,
                        help="If enabled, the deduplication process will not be performed and only test the last meaningful operation of a test case.")
    parser.add_argument("--keep_intermidiate_result", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the intermidiate result (e.g., execution trace, crash plans) of each test case will be kept (be careful of the mount point space).")
    parser.add_argument("--skip_umount", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, Silhouette skips the investigation of the umount function. Used for compare the running time with Chipmunk and Vinter.")
    parser.add_argument("--stop_after_tracing", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, this script runs only the execution-and-tracing phase. Other phases (e.g., deduplication, crash plan generation) will not be executed.")
    parser.add_argument("--stop_after_dedup", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, this script runs the execution-and-tracing and the deduplication phases. Other phases (e.g., crash plan generation) will not be executed.")
    parser.add_argument("--stop_after_cache_sim", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, this script runs the execution-and-tracing, the deduplication, and the cache simulating phases. Other phases (e.g., crash plan generation) will not be executed.")
    parser.add_argument("--stop_after_gen_crash_plan", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, this script runs the execution-and-tracing, the deduplication, and the crash plan generation phases. Other phases (e.g., recovery and validation) will not be executed.")
    parser.add_argument("--time_logger_local_file", type=str,
                        required=False, default=None,
                        help="The local logging file to store time elapsed information. If does not set, the time elapsed information will be logged in the logging file")
    parser.add_argument("--logging_file", type=str,
                        required=False, default=None,
                        help="The logging file")
    parser.add_argument("--logging_level", type=int,
                        required=False, default=40,
                        help="stderr output level:\n10: debug; 20: info ; 30: warning; 40: error; 50: critical. Default: 40.")
    parser.add_argument("--stderr_level", type=int,
                        required=False, default=50,
                        help="stderr output level:\n10: debug; 20: info ; 30: warning; 40: error; 50: critical. Default: 40.")

    args = parser.parse_args()
    print(args)

    if args.test_case_basename and args.test_case_basename == 'None':
        args.test_case_basename = None

    time_logger_local_file = args.time_logger_local_file
    env = EnvPhoney()

    logging_file = args.logging_file
    logging_level = args.logging_level
    stderr_level = args.stderr_level

    if env.GUEST_TIME_LOG_SEND_SERVER():
        log.setup_global_logger(fname=logging_file, file_lv=logging_level, stm=sys.stderr, stm_lv=stderr_level, time_fname=time_logger_local_file, host=env.TIME_LOG_SERVER_IP_ADDRESS_GUEST(), port=env.TIME_LOG_SERVER_PORT())

    else:
        log.setup_global_logger(fname=logging_file, file_lv=logging_level, stm=sys.stderr, stm_lv=stderr_level, time_fname=time_logger_local_file)

    return args

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.main.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

@timeit
def sync_clock():
    '''After restore a snapshot, the clock may deviate from the real clock'''
    cmd = 'sudo timedatectl set-timezone US/Eastern'
    shell_cl_local_run(cmd, ttl=10, crash_on_err=True)
    cmd = 'sudo timedatectl set-ntp true'
    shell_cl_local_run(cmd, ttl=10, crash_on_err=True)
    cmd = 'sudo systemctl restart systemd-timesyncd'
    shell_cl_local_run(cmd, ttl=10, crash_on_err=True)

@timeit
def restart_network():
    cmd = 'sudo systemctl restart systemd-networkd'
    shell_cl_local_run(cmd, ttl=10, crash_on_err=True)
    # cmd = 'sudo ifconfig enp0s2 down'
    # shell_cl_local_run(cmd, ttl=10, crash_on_err=True)
    # cmd = 'sudo ifconfig enp0s2 up'
    # shell_cl_local_run(cmd, ttl=10, crash_on_err=True)

def setup_env(fs_type):
    env = None
    if fs_type.upper() == 'NOVA':
        env = EnvNova()
    elif fs_type.upper() == 'PMFS':
        env = EnvPmfs()
    elif fs_type.upper() == 'WINEFS':
        env = EnvWinefs()
    else:
        msg = f"{traceback.format_exc()}\nInvalid file-system type: {fs_type}"
        log.global_logger.critical(msg)
        raise GuestExceptionForDebug(msg)
    return env

def setup_cheatsheet(fs_type):
    cheatsheet = None
    if fs_type.upper() == 'NOVA':
        cheatsheet = CheatSheetNova()
    elif fs_type.upper() == 'PMFS':
        cheatsheet = CheatSheetPMFS()
    elif fs_type.upper() == 'WINEFS':
        cheatsheet = CheatSheetWineFS()
    else:
        msg = f"{traceback.format_exc()}\nInvalid file-system type: {fs_type}"
        log.global_logger.critical(msg)
        raise GuestExceptionForDebug(msg)
    return cheatsheet

@timeit
def setup_ramfs(mnt_point, size):
    cmd = f'sudo mkdir -p {mnt_point}'
    shell_cl_local_run(cmd, ttl=10, crash_on_err=True)
    cmd = f'sudo mount -t tmpfs -o size={size}M tmpfs {mnt_point}'
    shell_cl_local_run(cmd, ttl=10, crash_on_err=True)
    cmd = f'sudo chmod 777 {mnt_point}'
    shell_cl_local_run(cmd, ttl=10, crash_on_err=True)

class GuestProc:
    def __init__(self, fs_type, vm_id, test_case_basename, args):
        self.args = args

        self.fs_type = fs_type
        self.vm_id = vm_id
        self.crash_plan_scheme = args.crash_plan_scheme
        self.env : EnvBase = setup_env(fs_type)
        self.cheatsheet = setup_cheatsheet(fs_type)

        self.require_mech = False
        if 'mech' in self.crash_plan_scheme:
            self.require_mech = True

        # since multiple threads use this same client, init with a pooled client.
        self.memcached_client : any[CMClient, CMPooledClient] = mc_wrapper.setup_memcached_pooled_client(self.env.MEMCACHED_IP_ADDRESS_GUEST(), self.env.MEMCACHED_PORT(), vm_id=self.vm_id)

        # set ramfs and directory to store result
        self.result_dir = self.env.GUEST_RESULT_STORE_DIR()
        self._init_dir()

        # set state
        self.set_state(GuestState.INITING)

        # init heartbeat
        self._init_heartbeat()

        # init the file system module
        self.fs_module = None
        self._init_fs_module()

        # get executable files
        self.exec_file_list = []
        # Sometimes, the VM may crash during testing a test case.
        # After a restart or restore, this VM needs to retest this case.
        # This variable is used to get the case that need to be retested.
        self.retest_exec_file = test_case_basename
        self._init_test_cases()

        # set state
        self.set_state(GuestState.INITED)

    @timeit
    def _init_dir(self):
        # set ramfs
        if self.env.GUEST_RAMFS_ENABLE():
            setup_ramfs(self.env.GUEST_RAMFS_MNT_POINT(), self.env.GUEST_RAMFS_SIZE())

        # create the dir to store result
        if not mkdirDirs(self.result_dir, exist_ok=True):
            msg = f"mkdir dir {self.result_dir} failed"
            log.global_logger.critical(msg)
            raise GuestExceptionForDebug

    @timeit
    def _init_heartbeat(self):
        key = f'heartbeat.{self.vm_id}'
        value = 0
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, value)
        start_heartbeat_service(self.memcached_client, key)

    @timeit
    def _init_fs_module(self):
        self.fs_module = ModuleDefault(self.env, ssh_alias_name='not_needed', local_run=True)
        self.fs_module.use_instrumented_ko()

        # clean up all mounted FS and modules
        self.fs_module.unmount_fs()
        self.fs_module.remove_module()

        # Create pmem namespace.
        # This command may not be needed if the dev is ready to use without namespace (e.g., simulate by the kernel command-line parameters)
        cmd = f'sudo ndctl create-namespace -t pmem -m fsdax -f -e namespace0.0'
        cl_state = shell_cl_local_run(cmd, ttl=90, crash_on_err=False)
        if cl_state.code != 0:
            msg = cl_state.msg("Create PM namespace failed: ")
            log.global_logger.critical(msg)
            raise GuestExceptionForDebug

    @timeit
    def _init_test_cases(self):
        found_retest_exec = False
        # get all executable files
        path_list = self.env.EXEC_FILES()
        for path in path_list:
            path = os.path.expanduser(path)
            path = os.path.abspath(path)

            no_exec_before = len(self.exec_file_list)
            log_msg = f'search exec from {path}'
            log.global_logger.debug(log_msg)

            if os.path.isfile(path) and os.access(path, os.X_OK):
                self.exec_file_list.append(path)
                if self.retest_exec_file and not found_retest_exec and os.path.basename(path) == self.retest_exec_file:
                    self.retest_exec_file = path
                    found_retest_exec = True

            elif os.path.isdir(path):
                for fpath in glob.glob(path + "/*"):
                    if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
                        self.exec_file_list.append(fpath)
                    if self.retest_exec_file and not found_retest_exec and os.path.basename(fpath) == self.retest_exec_file:
                        self.retest_exec_file = fpath
                        found_retest_exec = True

            else:
                for fpath in glob.glob(path):
                    if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
                        self.exec_file_list.append(fpath)
                    if self.retest_exec_file and not found_retest_exec and os.path.basename(fpath) == self.retest_exec_file:
                        self.retest_exec_file = fpath
                        found_retest_exec = True

            if self.retest_exec_file:
                if not os.path.isfile(self.retest_exec_file) or not os.access(self.retest_exec_file, os.X_OK):
                    log_msg = f'Did not found the to-retset test case {self.args.test_case_basename}, {self.retest_exec_file}'
                    log.global_logger.warning(log_msg)
                    self.retest_exec_file = None

            log_msg = f'found {len(self.exec_file_list) - no_exec_before} exec from {path}'
            log.global_logger.debug(log_msg)

        # Sort executable files so that all VMs have the same list of files, then we can use one global index in Memcached to atomically determine which case need to be run.
        def extract_first_int(fpath):
            basename = os.path.basename(fpath)
            match = re.search(r'\d+', basename)
            return int(match.group()) if match else 0

        self.exec_file_list.sort(key=extract_first_int, reverse=False)

        if self.args.shuffle_test_cases:
            random.seed(self.args.shuffle_seed)
            random.shuffle(self.exec_file_list)

    def _get_next_exec_idx_from_mc(self):
        key = 'next_exec_list_index'
        exec_idx = mc_wrapper.mc_incr_wrapper(self.memcached_client, key, 1)
        # since memcached only can increment non-negative number and will return the new value, we may miss the 0-th index. Thus, minors 1 to make sure all index can be visited.
        return exec_idx - 1

    def set_state(self, value):
        # set key-value pairs
        key = f'{self.vm_id}.state'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, value)

    def set_case_start(self, basename):
        key = f'{self.vm_id}.start'
        value = [basename, getTimestamp()]
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, value)

    def set_case_end(self, basename):
        key = f'{self.vm_id}.end'
        value = [basename, getTimestamp()]
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, value)

    @timeit
    def set_unique_op_indices(self, unique_indices, basename):
        # This key-value pair indicates to be tested operation indices
        key = f'{self.vm_id}.unique_indices'
        value = [basename, unique_indices]
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, value)

    def get_unique_indices(self):
        key = f'{self.vm_id}.unique_indices'
        value = mc_wrapper.mc_get_wrapper(self.memcached_client, key)
        if isinstance(value, list) and len(value) == 2:
            return value[0], value[1]
        else:
            return None, None

    @timeit
    def _fillfull_trace(self,  trace_reader : TraceReader, value_reader, instid_srcloc_reader):
        trace_reader.merge_value_entries(value_reader)
        trace_reader.merge_srcloc_entries(instid_srcloc_reader)

    @timeit
    def _load_oracle(self, case_dir):
        oracle_list = []
        fpath_list = []
        for fpath in glob.glob(f'{case_dir}/oracle_*.txt'):
            fpath_list.append(fpath)

        def extract_first_int(fpath):
            basename = os.path.basename(fpath)
            match = re.search(r'\d+', basename)
            return int(match.group()) if match else 0
        fpath_list.sort(key=extract_first_int)

        for fpath in fpath_list:
            ctx = CtxFileReader(fname=fpath)
            if not ctx.has_err_msg:
                oracle_list.append(ctx)
            else:
                msg = f"{fpath} has error msg:\n{str(ctx)}"
                log.global_logger.error(msg)
                # cannot trust all oracle files
                return []
        return oracle_list

    @timeit
    def _locate_oracle(self, fs_op_mgr : SplitOpMgr, oracle_list : list):
        msg = f"locate oracle: {[x.op_name for x in fs_op_mgr.op_entry_list]}"
        log.global_logger.debug(msg)
        msg = f"oracle list: {[x.fs_op.type.name() for x in oracle_list]}"
        log.global_logger.debug(msg)
        msg = f"fs op map: {self.env.FS_OP_MAP()}"
        log.global_logger.debug(msg)

        op_map = self.env.FS_OP_MAP()
        oracle_idx = 0
        for op_entry in fs_op_mgr.op_entry_list:
            op_entry : OpTraceEntry

            if oracle_idx >= len(oracle_list):
                if oracle_idx > 1:
                    op_entry.prev_op_oracle = oracle_list[oracle_idx - 1]
                continue

            ctx : CtxFileReader = oracle_list[oracle_idx]
            if ctx.fs_op.type.name() not in op_map:
                continue

            if op_entry.op_name in op_map[ctx.fs_op.type.name()]:
                op_entry.post_op_oracle = ctx
                if oracle_idx > 0:
                    op_entry.prev_op_oracle = oracle_list[oracle_idx - 1]
                oracle_idx += 1

            msg = f"match oracle: {op_entry.op_name}\n{str(op_entry.prev_op_oracle)}\n{str(op_entry.post_op_oracle)}"
            log.global_logger.debug(msg)

    @timeit
    def load_other_trace_info(self):
        value_reader = TraceValueReader(self.env.DUMP_TRACE_SV_FNAME())
        instid_srcloc_reader = InstIdSrcLocReader(self.env.INSTID_SRCLOC_MAP_FPATH())
        stinfo_reader = StructInfoReader(self.env.STRUCT_LAYOUT_FNAME())
        return value_reader, instid_srcloc_reader, stinfo_reader

    @timeit
    def write_cache_sim_result_to_local_file(self, case_dir : str, op_idx : int, op_entry : OpTraceEntry):
        result = op_entry.get_cache_analysis_result()
        fname = f'{case_dir}/{op_idx:02d}-{op_entry.op_name}-cachesim.result'
        with open(fname, 'w') as fd:
            fd.write(result)

    def _get_cache_sim_result_count_from_mc(self):
        key = 'cache_sim_result_count'
        num = mc_wrapper.mc_incr_wrapper(self.memcached_client, key, 1)
        return num

    @timeit
    def set_cache_sim_result_to_mc(self, case_dir : str, op_entry : OpTraceEntry, op_name_list):
        report_time = getTimestamp()
        num = self._get_cache_sim_result_count_from_mc()
        key = f'cache_sim_result.{num}'
        # value = op_entry.get_cache_analysis_result()
        # value = [os.path.basename(case_dir), op_name_list, value]
        value = [report_time, os.path.basename(case_dir), op_name_list, op_entry.in_fight_store_num, op_entry.num_cps_map, op_entry.mem_copy_list, op_entry.mem_set_list, op_entry.dup_flushes, op_entry.dup_fences, op_entry.unflushed_stores]
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, value)

    @timeit
    def cache_sim_analysis(self, op_entry : OpTraceEntry):
        cache = WitcherCache(EmptyBinaryFile())
        op_entry.analysis_in_cache_run(cache, ignore_nonatomic_write=False, nonatomic_as_one=True, sampling_nonatomic_write=False)

    @timeit
    def validating_cps(self, cp_scheme, case_dir, mem_image, op_entry, op_name_list, op_idx):
        for cp_idx in range(len(cp_scheme.cp_entry_list)):
            cp : CrashPlanEntry = cp_scheme.cp_entry_list[cp_idx]
            if cp.type.dummy_crash_plan():
                # cannot validate dummy crash plan
                continue
            validator.validate_crash_image(self.fs_module, self.env, self.memcached_client, case_dir, mem_image, op_entry, op_name_list[:op_idx+1], op_idx, cp, len(cp_scheme.cp_entry_list), cp_idx, self.args.dump_disk_content_to_disk, self.args.dump_crash_image_to_disk)

    @timeit
    def run_one_case_main(self, basename, fpath, case_dir, unique_op_indices):
        msg = f"going to test {basename}"
        log.global_logger.debug(msg)

        # 1. execution and tracing
        ret_code = False
        if self.args.stop_after_dedup:
            ret_code = tracing.tracing(self.memcached_client, self.fs_module, self.env, fpath, None)
        else:
            ret_code = tracing.tracing(self.memcached_client, self.fs_module, self.env, fpath, case_dir)
        if ret_code != 0:
            if ret_code == 199:
                # a magic code to indicate the stat failed.
                # some operations may do not yield error code and cannot state it (e.g., a symlink links to itself)
                tracing.insert_failed_ctx_test_case_to_memcached(basename, self.memcached_client)
                return True, ''
            elif ret_code == 200:
                tracing.insert_failed_umount_test_case_to_memcached(basename, self.memcached_client)
                return False, f'umount failed after running test case {basename}'
            else:
                # the executable file is failed to execute, e.g., rename a dir as its child
                tracing.insert_failed_test_case_to_memcached(basename, self.memcached_client)
                return True, ''

        if self.args.stop_after_tracing:
            return True, ''

        # 2. load trace and do some preprocessing
        trace_reader : TraceReader = dedup.load_trace(self.env)
        fs_op_mgr : SplitOpMgr = dedup.split_trace_by_fs_op(self.env, trace_reader)

        if len(fs_op_mgr.op_entry_list) == 0:
            return True, ''

        # 3. deduplicate
        if args.not_dedup:
            if unique_op_indices == None:
                unique_op_indices = []
                if args.not_dedup_test_last:
                    for op_idx in range(len(fs_op_mgr.op_entry_list) - 1, -1, -1):
                        op_entry : OpTraceEntry = fs_op_mgr.op_entry_list[op_idx]
                        if len(op_entry.pm_sorted_store_seq) == 0:
                            continue
                        elif 'super' in op_entry.op_name or 'module' in op_entry.op_name:
                            # do not test mount and rmmod
                            continue
                        else:
                            # if not dedup, we only test the last meaningful op
                            # otherwise we will test too much operations if we run > 1000 test cases
                            unique_op_indices = [op_idx]
                            break
                else:
                    for op_idx in range(0, len(fs_op_mgr.op_entry_list)):
                        unique_op_indices.append(op_idx)

            if len(unique_op_indices) == 0:
                # no unique operations need to investigate
                return True, ''

            msg = f'last op when not dedup: {fs_op_mgr.op_entry_list[unique_op_indices[0]].op_name}, {[x.op_name for x in fs_op_mgr.op_entry_list]}, {unique_op_indices}'
            log.global_logger.debug(msg)

        else:
            if unique_op_indices == None:
                unique_op_indices = dedup.deduplicate(self.memcached_client, fs_op_mgr, basename)

            if len(unique_op_indices) == 0:
                # no unique operations need to investigate
                return True, ''

            self.set_unique_op_indices(unique_op_indices, basename)

        if self.args.stop_after_dedup:
            return True, ''

        # 4. load other trace information when we need it here
        value_reader, instid_srcloc_reader, stinfo_reader = self.load_other_trace_info()
        value_reader : TraceValueReader
        instid_srcloc_reader : InstIdSrcLocReader
        stinfo_reader : StructInfoReader

        # 5. merge stored value and source location to the trace
        self._fillfull_trace(trace_reader, value_reader, instid_srcloc_reader)

        # 6. deduce the data type for trace
        stinfo_index : StInfoIndex = deducedatatype.deduce_data_type(self.env, trace_reader)

        # 7. init the mech deduce object
        mech_deduce : DeduceMech = DeduceMech(self.cheatsheet, self.memcached_client)
        if self.require_mech:
            # since we does not investigate the mount function, update the mech cheatsheet for it here
            mech_deduce.update_necessary_computations(trace_reader, op_entry=None, start_seq=0, end_seq=fs_op_mgr.op_entry_list[0].max_seq, is_mount_op=True)

        # 8. locate the oracle for each valueable operations. Some operations do not contain any PM stores (e.g., flush, read, opendir), we will ignore them.
        oracle_list = self._load_oracle(case_dir)
        self._locate_oracle(fs_op_mgr, oracle_list)

        op_name_list = [x.op_name for x in fs_op_mgr.op_entry_list]
        msg = f"list of vfs ops in {basename}: {op_name_list}"
        log.global_logger.debug(msg)

        mem_image = MemBinaryFile(basename, map_base=trace_reader.pm_addr, pmsize=trace_reader.pm_size)
        crashimage.put_trace_to_img(mem_image, trace_reader, 0, fs_op_mgr.op_entry_list[0].min_seq)

        # iterate each op
        for op_idx in range(len(fs_op_mgr.op_entry_list)):
            op_entry : OpTraceEntry = fs_op_mgr.op_entry_list[op_idx]
            msg = f"fs op name: {op_entry.op_name}"
            log.global_logger.debug(msg)

            try:
                if self.args.skip_umount and 'put_super' in op_entry.op_name:
                    continue

                if op_idx not in unique_op_indices or len(op_entry.pm_sorted_store_seq) == 0:
                    if self.require_mech:
                        # even if this operation is not a unique operation, we still would like to update necessary mech cheatsheet
                        mech_deduce.update_necessary_computations(None, op_entry=op_entry, start_seq=op_entry.min_seq, end_seq=op_entry.max_seq, is_mount_op=False)
                    continue

                msg = f"testing fs op name: {op_entry.op_name}"
                log.global_logger.debug(msg)

                # 8. generate performance bug and in-flight cluster maps
                self.cache_sim_analysis(op_entry)
                self.set_cache_sim_result_to_mc(case_dir, op_entry, op_name_list[:op_idx+1])
                if self.args.keep_intermidiate_result:
                    self.write_cache_sim_result_to_local_file(case_dir, op_idx, op_entry)

                if self.args.stop_after_cache_sim:
                    continue

                # 9. generate oracle state if it does not have
                validator.get_prev_oracle(self.fs_module, self.env, self.memcached_client, case_dir, mem_image, op_entry, op_name_list[:op_idx+1])
                validator.get_post_oracle(self.fs_module, self.env, self.memcached_client, case_dir, mem_image, op_entry, op_name_list[:op_idx+1])
                if not op_entry.prev_op_oracle or not op_entry.post_op_oracle:
                    msg = f"cannot get the prev/post operation oracle for {op_name_list[:op_idx+1]}"
                    log.global_logger.error(msg)
                    continue

                if self.args.dump_disk_content_to_disk:
                    fpath = f'{case_dir}/{op_idx:02d}-{op_entry.op_name}-prev-oracle.ctx'
                    validator.dump_ctx_to_disk(fpath, op_entry.prev_op_oracle)
                    fpath = f'{case_dir}/{op_idx:02d}-{op_entry.op_name}-post-oracle.ctx'
                    validator.dump_ctx_to_disk(fpath, op_entry.post_op_oracle)

                # 10. generate crash plans
                mech_deduce.clean()
                mech_deduce.set_info(basename, op_name_list[:op_idx+1])
                cp_scheme = crashplan.generate_crash_plans(trace_reader, stinfo_index, op_entry, mech_deduce, self.crash_plan_scheme, ignore_nonatomic_write=False, nonatomic_as_one=False, sampling_nonatomic_write=True)

                existing_key = f'{basename}.{op_idx}.crash.plan.existing'
                cp_scheme.send_to_memcached(self.memcached_client, existing_key=existing_key)
                if self.args.dump_crash_plan_to_disk:
                    cp_scheme.write_to_disk(case_dir, f'{op_idx:02d}-{op_entry.op_name}', use_pickle=False)

                if self.args.stop_after_gen_crash_plan:
                    continue

                # 11. validating
                self.validating_cps(cp_scheme, case_dir, mem_image, op_entry, op_name_list, op_idx)
                # for cp_idx in range(len(cp_scheme.cp_entry_list)):
                #     cp : CrashPlanEntry = cp_scheme.cp_entry_list[cp_idx]
                #     validator.validate_crash_image(self.fs_module, self.env, self.memcached_client, case_dir, mem_image, op_entry, op_name_list[:op_idx+1], op_idx, cp, cp_idx, self.args.dump_disk_content_to_disk)

            except Exception as e:
                raise

            finally:
                # update the image
                msg = f"update image at finally"
                log.global_logger.debug(msg)
                crashimage.put_op_trace_to_img(mem_image, op_entry, op_entry.min_seq, op_entry.max_seq + 1)

                if self.args.dump_crash_image_to_disk and len(op_entry.pm_sorted_store_seq) > 0:
                    fpath = f'{case_dir}/{op_idx:02d}-{op_entry.op_name}-post.img'
                    mem_image.dumpToFile(fpath)

        return True, ''

    @timeit
    def run_one_case(self, fpath, unique_op_indices):
        basename = os.path.basename(fpath)
        self.set_case_start(basename)

        case_dir = f'{self.result_dir}/{basename}'
        if not mkdirDirs(case_dir, exist_ok=True):
            log.global_logger.error(f'mkdir {case_dir} failed.')
            raise GuestExceptionForDebug(f'mkdir {case_dir} failed.')

        succ, msg = self.run_one_case_main(basename, fpath, case_dir, unique_op_indices)

        self.set_case_end(basename)

        if not succ:
            raise GuestExceptionToRestartVM(msg)

        if not self.args.keep_intermidiate_result:
            removeDir(case_dir, force=True)

    @timeit
    def run(self, num_cases_to_test):
        num_tested_cases = 0
        self.set_state(GuestState.RUNNING)

        msg = f"exec list: {self.exec_file_list}"
        log.global_logger.debug(msg)

        if self.retest_exec_file:
            num_tested_cases += 1
            retest_basename, unique_op_indices = self.get_unique_indices()
            if retest_basename == None or unique_op_indices == None or retest_basename != os.path.basename(self.retest_exec_file):
                msg = f"retest {self.retest_exec_file} without index information"
                log.global_logger.debug(msg)
                self.run_one_case(self.retest_exec_file, None)
            else:
                msg = f"retest {self.retest_exec_file} with index information"
                log.global_logger.debug(msg)
                self.run_one_case(self.retest_exec_file, unique_op_indices)

        while True:
            num_tested_cases += 1

            if num_tested_cases > num_cases_to_test:
                break

            exec_idx = self._get_next_exec_idx_from_mc()
            if exec_idx >= len(self.exec_file_list):
                log_msg = f'got exec_idx {exec_idx} >= {len(self.exec_file_list)}'
                log.global_logger.debug(log_msg)
                break
            exec_fpath = self.exec_file_list[exec_idx]

            self.run_one_case(exec_fpath, None)

        stop_heartbeat_service()
        self.set_state(GuestState.COMPLETE)

def main(args):
    fs_type = args.fs_type
    test_case_basename = args.test_case_basename
    vm_id = args.vm_id
    num_cases_to_test = args.num_cases_to_test

    sys.excepthook = handle_uncaught_exception
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    sync_clock()

    guest_proc = GuestProc(fs_type, vm_id, test_case_basename, args)
    guest_proc.run(num_cases_to_test)

if __name__ == "__main__":
    args = parse_args()
    main(args)
