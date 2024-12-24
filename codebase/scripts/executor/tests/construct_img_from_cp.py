import os
import sys
import argparse
from distutils.util import strtobool
import time
import traceback
import re
import threading
import glob
import pickle
import copy
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
from tools.disk_content.disk_content_wrap import call_get_content
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
    parser.add_argument("--crash_plan_path", type=str,
                        required=True, default=None,
                        help="The path to the crash plan.")
    parser.add_argument("--trace_file", type=str,
                        required=True, default=None,
                        help="The path to the crash plan.")
    parser.add_argument("--trace_sv_file", type=str,
                        required=True, default=None,
                        help="The path to the crash plan.")
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

def init_fs_module(env):
    fs_module = ModuleDefault(env, ssh_alias_name='not_needed', local_run=True)
    fs_module.use_instrumented_ko()

    # clean up all mounted FS and modules
    fs_module.unmount_fs()
    fs_module.remove_module()

    # Create pmem namespace.
    # This command may not be needed if the dev is ready to use without namespace (e.g., simulate by the kernel command-line parameters)
    cmd = f'sudo ndctl create-namespace -t pmem -m fsdax -f -e namespace0.0'
    cl_state = shell_cl_local_run(cmd, ttl=90, crash_on_err=False)
    if cl_state.code != 0:
        msg = cl_state.msg("Create PM namespace failed: ")
        log.global_logger.critical(msg)
        assert False, msg

    return fs_module

def get_fs_state_thd(path : str, env : EnvBase):
    # thread version should outperform the popen version.
    # creating and starting a thread take ~ 200 ms.
    def local_get_fs_state(path, rst_list):
        ctx_str = call_get_content(path, "NA")
        if log.debug:
            msg = f"ctx str: {ctx_str}"
            log.global_logger.debug(msg)
        if ctx_str:
            ctx = CtxFileReader(lines=ctx_str)
            rst_list[0] = ctx
        return 0

    rst_list = [None]
    thd = threading.Thread(target=local_get_fs_state, args=(path, rst_list), daemon=True)
    thd.start()
    # timeout in 10 seconds
    thd.join(10)
    if isinstance(rst_list[0], CtxFileReader):
        return rst_list[0]
    else:
        return None

def get_fs_state(path) -> CtxFileReader:
    ctx_str = call_get_content(path, "NA")
    msg = f"ctx str: {ctx_str}"
    log.global_logger.debug(msg)
    if ctx_str:
        ctx = CtxFileReader(lines=ctx_str)
        return ctx
    return None

def main(args):
    fs_type = args.fs_type
    crash_plan_path = args.crash_plan_path
    trace_file = args.trace_file
    trace_sv_file = args.trace_sv_file

    env : EnvBase = setup_env(fs_type)
    fs_module = init_fs_module(env)
    fs_module.use_raw_ko()

    trace_reader : TraceReader = TraceReader(trace_file)
    fs_op_mgr : SplitOpMgr = dedup.split_trace_by_fs_op(env, trace_reader)

    value_reader = TraceValueReader(trace_sv_file)
    instid_srcloc_reader = InstIdSrcLocReader(env.INSTID_SRCLOC_MAP_FPATH())
    stinfo_reader = StructInfoReader(env.STRUCT_LAYOUT_FNAME())

    trace_reader.merge_value_entries(value_reader)
    trace_reader.merge_srcloc_entries(instid_srcloc_reader)
    stinfo_index : StInfoIndex = deducedatatype.deduce_data_type(env, trace_reader)

    cp : CrashPlanEntry = None
    with open(crash_plan_path, 'rb') as fd:
        cp = pickle.load(fd)
    cp_state_generated = False

    mem_image = MemBinaryFile("baseame", map_base=trace_reader.pm_addr, pmsize=trace_reader.pm_size)
    crashimage.put_trace_to_img(mem_image, trace_reader, 0, fs_op_mgr.op_entry_list[0].min_seq)

    for op_idx in range(len(fs_op_mgr.op_entry_list)):
        op_entry : OpTraceEntry = fs_op_mgr.op_entry_list[op_idx]

        if len(op_entry.pm_sorted_store_seq) == 0:
            continue

        msg = f"{op_entry.op_name}, [{op_entry.min_seq}, {op_entry.max_seq}], {cp.start_seq}, {len(op_entry.pm_sorted_store_seq)}"
        log.global_logger.debug(msg)
        print(msg)

        try:
        # if cp.start_seq > op_entry.max_seq or cp.start_seq < op_entry.min_seq:
        #     crashimage.put_op_trace_to_img(mem_image, op_entry, op_entry.min_seq, op_entry.max_seq + 1)
        # else:
            # get prev-op state
            img_cpy1 = mem_image.copy("prev_op")
            img_cpy1.dumpToDev(env.MOD_DEV_PATH())
            img_cpy1.dumpToFile(f'/tmp/{op_idx}-{op_entry.op_name}-xx_prev_op.img')
            validator.remount_fs(fs_module)
            prev_ctx = get_fs_state(env.MOD_MNT_POINT())
            validator.dump_ctx_to_disk(f'/tmp/{op_idx}-{op_entry.op_name}-xx_prev_op.ctx', prev_ctx)
            validator.unmount_fs(fs_module)
            print(f"prev-op state generated")

            # get post-op state
            # for seq in op_entry.pm_sorted_store_seq:
            #     if seq < op_entry.min_seq:
            #         continue
            #     if seq >= op_entry.max_seq + 1:
            #         break

            #     op = op_entry.pm_seq_entry_map[seq][0]
            #     if op.type.isStoreSeries() and op.sv_entry:
            #         msg = f"{op.seq}, {str(op.stinfo_match)}, {str(op.var_list)}\n"
            #         log.global_logger.debug(msg)

            img_cpy2 = mem_image.copy("post_op")
            crashimage.put_op_trace_to_img(img_cpy2, op_entry, op_entry.min_seq, op_entry.max_seq + 1)
            img_cpy2.dumpToDev(env.MOD_DEV_PATH())
            img_cpy2.dumpToFile(f'/tmp/{op_idx}-{op_entry.op_name}-xx_post_op.img')
            validator.remount_fs(fs_module)
            post_ctx = get_fs_state(env.MOD_MNT_POINT())
            validator.dump_ctx_to_disk(f'/tmp/{op_idx}-{op_entry.op_name}-xx_post_op.ctx', post_ctx)
            validator.unmount_fs(fs_module)
            print(f"post-op state generated")

            # get crash state
            if op_entry.min_seq <= cp.start_seq <= op_entry.max_seq and not cp_state_generated:
                crashimage.put_op_trace_to_img(mem_image, op_entry, op_entry.min_seq, op_entry.max_seq + 1)
                img_cpy3 = mem_image.copy("crash_plan")
                crashimage.put_cp_to_img(img_cpy3, op_entry, cp)
                img_cpy3.dumpToDev(env.MOD_DEV_PATH())
                img_cpy3.dumpToFile(f'/tmp/{op_idx}-{op_entry.op_name}-xx_crash.img')
                validator.remount_fs(fs_module)
                cp_ctx = get_fs_state(env.MOD_MNT_POINT())
                validator.dump_ctx_to_disk(f'/tmp/{op_idx}-{op_entry.op_name}-xx_crash_op.ctx', cp_ctx)
                validator.unmount_fs(fs_module)
                cp_state_generated = True
                print(f"crash state generated")

        finally:
            crashimage.put_op_trace_to_img(mem_image, op_entry, op_entry.min_seq, op_entry.max_seq + 1)

if __name__ == "__main__":
    args = parse_args()
    main(args)
