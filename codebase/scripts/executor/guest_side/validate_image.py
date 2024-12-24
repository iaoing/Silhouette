import os
import sys
import time
import traceback
import threading
import copy
from enum import Enum
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
from tools.disk_content.disk_content_wrap import call_get_content
from tools.scripts.disk_content.disk_content_diff import diff_ctx
from tools.scripts.disk_content.disk_content import CtxFileReader
from tools.scripts.disk_content.dentry_attr import DiskEntryAttrs
from workload.filesystem_operations.fsop_type import FSOpType
from scripts.utils.utils import getTimestamp, fileExists, dirExists, generate_random_string
from scripts.vm_comm.heartbeat_guest import start_heartbeat_service, stop_heartbeat_service
import scripts.vm_comm.memcached_lock as mc_lock
import scripts.vm_comm.memcached_wrapper as mc_wrapper
import scripts.shell_wrap.shell_cmd_helper as shell_cmd
from scripts.shell_wrap.shell_local_run import shell_cl_local_run, ShellCLState
from scripts.crash_plan.crash_plan_entry import CrashPlanEntry, CrashPlanSamplingType, CrashPlanType
from scripts.crash_plan.crash_plan_scheme_base import CrashPlanSchemeBase
from scripts.crash_plan.crash_plan_scheme_2cp import CrashPlanScheme2CP
from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot, GuestExceptionForValidation
import scripts.executor.guest_side.generate_crash_image as crashimage
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.validate.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class ValidateRstType(Enum):
    """The types of validation result."""
    GOOD                 = 'good'

    # fatal errors that need to reboot the vm
    REMOUNT_FAILED       = 'remount_failed'
    UMOUNT_FAILED        = 'umount_failed'
    GET_FS_STATE_FAILED  = 'get_fs_state_failed'
    SYSLOG_ERROR         = 'syslog_error'
    READ_SYSLOG_FAILED   = 'read_syslog_failed'
    CANNOT_READ          = 'cannot_read'
    CANNOT_WRITE         = 'cannot_write'
    CANNOT_REMOVE        = 'cannot_remove'

    # fatal errors that need to reboot the vm
    GET_PREV_ORACLE_REMOUNT_FAILED     = 'get_prev_oracle_remount_failed'
    GET_PREV_ORACLE_GET_FS_STAT_FAILED = 'get_prev_oracle_get_fs_stat_failed'
    GET_PREV_ORACLE_UMOUNT_FAILED      = 'get_prev_oracle_umount_failed'
    GET_POST_ORACLE_GET_FS_STAT_FAILED = 'get_post_oracle_get_fs_stat_failed'
    GET_POST_ORACLE_REMOUNT_FAILED     = 'get_post_oracle_remount_failed'
    GET_POST_ORACLE_UMOUNT_FAILED      = 'get_post_oracle_umount_failed'

    MATCH_PREV_ORACLE = 'match_prev_oracle'
    MATCH_POST_ORACLE = 'match_post_oracle'
    MISMATCH_BOTH_ORACLE = 'mismatch_both_oracle'

    MISMATCH_OLD_VALUE   = 'mismatch_old_value'
    MISMATCH_NEW_VALUE   = 'mismatch_new_value'

    SEMANTIC_BUG_DIFF_DINO_STINO        = 'semantic_bug_diff_dino_stino'
    SEMANTIC_BUG_DUPLICATE_INO          = 'semantic_bug_duplicate_ino'
    SEMANTIC_BUG_DIFF_DOT_INO           = 'semantic_bug_diff_dot_ino'
    SEMANTIC_BUG_DIFF_DOTDOT_INO        = 'semantic_bug_diff_dotdot_ino'
    SEMANTIC_BUG_FILE_SIZE_AFTER_APPEND = 'semantic_bug_file_size_after_append'
    SEMANTIC_BUG_FILE_SIZE_AFTER_WRITE  = 'semantic_bug_file_size_after_write'
    SEMANTIC_BUG_DIFF_STATE_BEFORE_AND_AFTER_UMOUNT  = 'semantic_bug_diff_state_before_and_after_umount'

    UNKNOWN              = 'unknown'

    def cannot_continue_check(self) -> bool:
        return any(self is x for x in [ValidateRstType.REMOUNT_FAILED, ValidateRstType.UMOUNT_FAILED, ValidateRstType.GET_FS_STATE_FAILED, ValidateRstType.SYSLOG_ERROR, ValidateRstType.READ_SYSLOG_FAILED, ValidateRstType.CANNOT_READ, ValidateRstType.CANNOT_WRITE, ValidateRstType.CANNOT_REMOVE, ValidateRstType.GET_PREV_ORACLE_REMOUNT_FAILED, ValidateRstType.GET_PREV_ORACLE_GET_FS_STAT_FAILED, ValidateRstType.GET_PREV_ORACLE_UMOUNT_FAILED, ValidateRstType.GET_POST_ORACLE_GET_FS_STAT_FAILED, ValidateRstType.GET_POST_ORACLE_REMOUNT_FAILED, ValidateRstType.GET_POST_ORACLE_UMOUNT_FAILED])

def _get_unique_count_by_incr(memcached_client, key):
    num = mc_wrapper.mc_incr_wrapper(memcached_client, key, 1)
    return num

def add_cp_and_validate_rst_to_mc(memcached_client, case_dir, op_name_list, op_idx, total_cps, cp_idx, tp: ValidateRstType):
    if tp != ValidateRstType.GOOD:
        report_time = getTimestamp()
        key = 'crash_plan_to_validate_rst'
        num = _get_unique_count_by_incr(memcached_client, key)

        key = f'crash_plan_to_validate_rst.{num}'
        value = [report_time, os.path.basename(case_dir), op_name_list, op_idx, total_cps, cp_idx, tp.value]
        mc_wrapper.mc_set_wrapper(memcached_client, key, value)

@timeit
def proc_validate_result(tp: ValidateRstType, memcached_client, case_dir, op_entry : OpTraceEntry, op_name_list : list, cp : CrashPlanEntry, other_msg, existkey_msg):
    report_time = getTimestamp()
    if existkey_msg == None:
        key = f'ValidateRstType.{tp.value}.count'
        num = _get_unique_count_by_incr(memcached_client, key)
        ret, dmesg_log = get_syslog()

        key = f'ValidateRstType.{tp.value}.{num}'
        value = [report_time, os.path.basename(case_dir), op_name_list, cp, dmesg_log, other_msg]
        mc_wrapper.mc_set_wrapper(memcached_client, key, value)

    else:
        existing_key = f'ValidateRstType.{tp.value}.{op_name_list[-1]}.{existkey_msg}'
        existing_key = str(hash(existing_key))
        if mc_wrapper.mc_add_wrapper(memcached_client, existing_key, '1'):

            key = f'ValidateRstType.{tp.value}.count'
            num = _get_unique_count_by_incr(memcached_client, key)
            ret, dmesg_log = get_syslog()

            key = f'ValidateRstType.{tp.value}.{num}'
            value = [report_time, os.path.basename(case_dir), op_name_list, cp, dmesg_log, other_msg]
            mc_wrapper.mc_set_wrapper(memcached_client, key, value)

    msg = f"validation failed: {tp.value} for case {os.path.basename(case_dir)} in op {op_name_list}, {other_msg}"
    log.global_logger.error(msg)
    log.flush_all()

    if tp.cannot_continue_check():
        raise GuestExceptionForValidation(msg)

def found_key_exist(memcached_client, tp: ValidateRstType, found_key : str):
    # this is not thread-safe, but it does not matter.
    hash_key = f'foundkey:ValidateRstType.{tp.value}-{found_key}'
    hash_key = str(hash(hash_key))
    value = mc_wrapper.mc_get_wrapper(memcached_client, hash_key)
    return value != None

def found_key_insert(memcached_client, tp: ValidateRstType, found_key : str):
    # this is not thread-safe, but it does not matter.
    hash_key = f'foundkey:ValidateRstType.{tp.value}-{found_key}'
    hash_key = str(hash(hash_key))
    mc_wrapper.mc_set_wrapper(memcached_client, hash_key, 1)

@timeit
def remount_fs(fs_module : ModuleDefault) -> bool:
    if not fs_module.insert_module():
        msg = f'{traceback.format_exc()}\nInsert module failed!'
        log.global_logger.critical(msg)
        raise GuestExceptionToRestartVM(msg)

    if not fs_module.remount_fs():
        # something wrong with the image
        msg = f'{traceback.format_exc()}\nRemount failed!'
        log.global_logger.error(msg)
        return False

    return True

@timeit
def unmount_fs(fs_module : ModuleDefault) -> bool:
    if not fs_module.unmount_fs():
        # something wrong with the image
        msg = f'{traceback.format_exc()}\nUmount failed!'
        log.global_logger.error(msg)
        return False

    if not fs_module.remove_module():
        msg = f'{traceback.format_exc()}\nRemove module failed!'
        log.global_logger.critical(msg)
        raise GuestExceptionToRestartVM(msg)

    return True

@timeit
def dump_img_to_dev(img : MemBinaryFile, dev_path : str):
    '''
    The sudo permission required. Please run the main script as sudo.
    '''
    img.dumpToDev(dev_path)

@timeit
def dump_ctx_to_disk(fpath : str, ctx : CtxFileReader):
    with open(fpath, 'w') as fd:
        fd.writelines(ctx.lines)

@timeit
def get_fs_state_proc(path : str, env : EnvBase):
    ofile = '/tmp/disk_content_tmp.txt'
    desc = 'validation_script'
    exec_fpath = env.DUMP_DISK_CONTENT_EXE()
    cmd = f'sudo {exec_fpath} {path} {ofile} {desc}'
    cl_state : ShellCLState = shell_cl_local_run(cmd, 10, False)
    if cl_state.code != 0:
        msg = f"dump disk content failed: {cl_state.msg()}"
        log.global_logger.warning(msg)
        return None
    else:
        ctx : CtxFileReader = CtxFileReader(fname=ofile)
        return ctx

@timeit
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

@timeit
def get_fs_state(path) -> CtxFileReader:
    # Do not why sometimes the script hangs at this function
    # Please use above function so that we can have a TTL
    ctx_str = call_get_content(path, "NA")
    if log.debug:
        msg = f"ctx str: {ctx_str}"
        log.global_logger.debug(msg)
    if ctx_str:
        ctx = CtxFileReader(lines=ctx_str)
        return ctx
    return None

@timeit
def get_prev_oracle(fs_module : ModuleDefault, env : EnvBase, memcached_client, case_dir, img : MemBinaryFile, op_entry : OpTraceEntry, op_name_list : list):
    if op_entry.prev_op_oracle:
        return

    fs_module.use_raw_ko()

    dump_img_to_dev(img, env.MOD_DEV_PATH())
    if not remount_fs(fs_module):
        proc_validate_result(ValidateRstType.GET_PREV_ORACLE_REMOUNT_FAILED, memcached_client, case_dir, op_entry, op_name_list, None, None, None)

    op_entry.prev_op_oracle = get_fs_state_thd(env.MOD_MNT_POINT(), env)
    if not op_entry.prev_op_oracle:
        proc_validate_result(ValidateRstType.GET_PREV_ORACLE_GET_FS_STAT_FAILED, memcached_client, case_dir, op_entry, op_name_list, None, None, None)

    if not unmount_fs(fs_module):
        proc_validate_result(ValidateRstType.GET_PREV_ORACLE_UMOUNT_FAILED, memcached_client, case_dir, op_entry, op_name_list, None, None, None)

# @timeit
# do not timing it since the elapsed time is ~2 macroseconds, which is less than the time to send msg to the server (~140 macroseconds).
# indeed, the post oracle are already obtained during running the test case
def get_post_oracle(fs_module : ModuleDefault, env : EnvBase, memcached_client, case_dir, img : MemBinaryFile, op_entry : OpTraceEntry, op_name_list : list):
    if op_entry.post_op_oracle:
        return

    fs_module.use_raw_ko()

    img_copy = img.copy('post_oracle')
    crashimage.put_op_trace_to_img(img_copy, op_entry, op_entry.min_seq, op_entry.max_seq + 1)

    dump_img_to_dev(img_copy, env.MOD_DEV_PATH())
    if not remount_fs(fs_module):
        proc_validate_result(ValidateRstType.GET_POST_ORACLE_REMOUNT_FAILED, memcached_client, case_dir, op_entry, op_name_list, None, None, None)

    op_entry.post_op_oracle = get_fs_state_thd(env.MOD_MNT_POINT(), env)
    if not op_entry.post_op_oracle:
        proc_validate_result(ValidateRstType.GET_POST_ORACLE_GET_FS_STAT_FAILED, memcached_client, case_dir, op_entry, op_name_list, None, None, None)

    if not unmount_fs(fs_module):
        proc_validate_result(ValidateRstType.GET_POST_ORACLE_UMOUNT_FAILED, memcached_client, case_dir, op_entry, op_name_list, None, None, None)

# @timeit
# do not timing it since the elapsed time is ~71 macroseconds, which is less than the time to send msg to the server (~140 macroseconds).
def check_oracles(recovery_stat : CtxFileReader, op_entry : OpTraceEntry, env : EnvBase) -> ValidateRstType:
    prev_diff_str, prev_diff_num = diff_ctx(recovery_stat.get_entry_path_map(), op_entry.prev_op_oracle.get_entry_path_map(), env.IGNORE_STAT_ATTR_SET())

    post_diff_str, post_diff_num = diff_ctx(recovery_stat.get_entry_path_map(), op_entry.post_op_oracle.get_entry_path_map(), env.IGNORE_STAT_ATTR_SET())

    if prev_diff_num > 0 and post_diff_num > 0:
        existing_msg = f'{prev_diff_str}{post_diff_str}'
        msg = f'compare with prev-op state (- is recovered stat):\n{prev_diff_str}compare with post-op state (- is recovered stat):\n{post_diff_str}\nprev_stat:\n{"".join(x for x in op_entry.prev_op_oracle.lines)}\npost_stat:\n{"".join(x for x in op_entry.post_op_oracle.lines)}\nrecovered_stat:\n{"".join(x for x in recovery_stat.lines)}'
        return ValidateRstType.MISMATCH_BOTH_ORACLE, msg, existing_msg
    elif prev_diff_num == 0:
        return ValidateRstType.MATCH_PREV_ORACLE, None, None
    elif post_diff_num == 0:
        return ValidateRstType.MATCH_POST_ORACLE, None, None
    else:
        # only possible for a non-sequential operation, e.g., umount
        return ValidateRstType.GOOD, None, None

@timeit
def check_recovered_content(memcached_client, env : EnvBase, op_entry : OpTraceEntry, cp : CrashPlanEntry, check_old_value : bool = False, check_new_value : bool = False):
    if cp.type.no_content_to_check() or (not check_old_value and not check_new_value) or (not cp.exp_data_seqs) or (len(cp.exp_data_seqs) == 0):
        return ValidateRstType.GOOD, None

    with open(env.MOD_DEV_PATH(), 'rb') as fd:
        for seq in cp.exp_data_seqs:
            trace_entry : TraceEntry = op_entry.pm_seq_entry_map[seq][0]

            found_key = f'{op_entry.op_name}.{trace_entry.instid}'
            # found_key = f'{op_entry.op_name}' # simplify the key to save space
            found_key_in_old = found_key_exist(memcached_client, ValidateRstType.MISMATCH_OLD_VALUE, found_key)
            found_key_in_new = found_key_exist(memcached_client, ValidateRstType.MISMATCH_NEW_VALUE, found_key)
            if check_old_value and check_new_value and found_key_in_old and found_key_in_new:
                continue
            elif check_old_value and found_key_in_old:
                continue
            elif check_new_value and found_key_in_new:
                continue

            offset = trace_entry.addr - op_entry.pm_addr
            fd.seek(offset)
            rec_data = fd.read(trace_entry.size)

            if check_old_value and trace_entry.ov_entry.data != rec_data:
                found_key_insert(memcached_client, ValidateRstType.MISMATCH_OLD_VALUE, found_key)
                msg = f"match prev oracle but mismatch the old content: {trace_entry}, {str(cp)}"
                log.global_logger.error(msg)
                return ValidateRstType.MISMATCH_OLD_VALUE, msg
            if check_old_value and trace_entry.sv_entry.data != rec_data:
                found_key_insert(memcached_client, ValidateRstType.MISMATCH_NEW_VALUE, found_key)
                msg = f"match post oracle but mismatch the new content: {trace_entry}, {str(cp)}"
                log.global_logger.error(msg)
                return ValidateRstType.MISMATCH_NEW_VALUE, msg

    return ValidateRstType.GOOD, None

@timeit
def clear_syslog():
    # clear the kernel ring buffer
    cmd = 'dmesg -C'
    shell_cl_local_run(cmd, 10, False)

@timeit
def get_syslog():
    cmd = "dmesg"
    cl_state : ShellCLState = shell_cl_local_run(cmd, 30, False)
    if cl_state.code != 0:
        msg = f"Execute demsg failed: {cl_state.msg()}"
        log.global_logger.warning(msg)
        return False, cl_state.msg()
    else:
        return True, cl_state.stdout.decode("utf-8", errors='ignore')

@timeit
def check_syslog():
    ret, log_msg = get_syslog()
    if not ret:
        return ValidateRstType.READ_SYSLOG_FAILED, log_msg
    elif 'PANIC' in log_msg or 'RIP: ' in log_msg or 'BUG' in log_msg or 'nova error' in log_msg or 'pmfs error' in log_msg or 'winefs error' in log_msg:
        return ValidateRstType.SYSLOG_ERROR, log_msg
    return ValidateRstType.GOOD, None

# @timeit
# do not timing it since the elapsed time is ~33 macroseconds, which is less than the time to send msg to the server (~140 macroseconds).
def check_fs_semantic(memcached_client, op_entry : OpTraceEntry, env : EnvBase):
    if op_entry.post_op_oracle.fs_op.type == FSOpType.OP_CREATE:
        fpath = op_entry.post_op_oracle.fs_op.file_path
        fpath_d_ino = op_entry.post_op_oracle.entries_path_map[fpath].vars['Dir_Inode']
        fpath_st_ino = op_entry.post_op_oracle.entries_path_map[fpath].vars['File_Inode']
        # do not check whether the d_ino and st_ino are the same, since file do not have a d_ino in dirent.
        # if not found_key_exist(memcached_client, ValidateRstType.SEMANTIC_BUG_DIFF_DINO_STINO, '') and fpath_d_ino != fpath_st_ino:
        #     msg = f"a newly created file has different d_ino and st_ino:\n{str(op_entry.post_op_oracle.entries_path_map[fpath])}"
        #     log.global_logger.error(msg)
        #     return ValidateRstType.SEMANTIC_BUG_DIFF_DINO_STINO, msg
        if not found_key_exist(memcached_client, ValidateRstType.SEMANTIC_BUG_DUPLICATE_INO, ''):
            # check ino is different from other entries in the prev oracle
            for chkpath, attrs in op_entry.prev_op_oracle.entries_path_map.items():
                if chkpath == fpath:
                    continue
                chkpath_d_ino = attrs.vars['Dir_Inode']
                chkpath_st_ino = attrs.vars['File_Inode']
                if fpath_st_ino == chkpath_st_ino:
                    msg = f"a newly created file has a duplicate ino with prev-op file:\nprev attrs:\n{str(attrs)}\nthis attrs:\n{str(op_entry.post_op_oracle.entries_path_map[fpath])}"
                    log.global_logger.error(msg)
                    return ValidateRstType.SEMANTIC_BUG_DUPLICATE_INO, msg
            # check ino is different from other entries in the post oracle
            for chkpath, attrs in op_entry.post_op_oracle.entries_path_map.items():
                if chkpath == fpath:
                    continue
                chkpath_d_ino = attrs.vars['Dir_Inode']
                chkpath_st_ino = attrs.vars['File_Inode']
                if fpath_st_ino == chkpath_st_ino:
                    msg = f"a newly created file has a duplicate ino with post-op file:\npost attrs:\n{str(attrs)}\nthis attrs:\n{str(op_entry.post_op_oracle.entries_path_map[fpath])}"
                    log.global_logger.error(msg)
                    return ValidateRstType.SEMANTIC_BUG_DUPLICATE_INO, msg

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_UNLINK:
        # what should be checked here
        pass

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_MKDIR:
        # for dir inside the same mountpoint, the d_ino and st_ino should be the same
        # https://www.kernel.org/doc/html/v5.12/filesystems/overlayfs.html#inode-properties
        dpath = op_entry.post_op_oracle.fs_op.dir_path.rstrip('/')
        dpath_d_ino = op_entry.post_op_oracle.entries_path_map[dpath].vars['Dir_Inode']
        dpath_st_ino = op_entry.post_op_oracle.entries_path_map[dpath].vars['File_Inode']
        if not found_key_exist(memcached_client, ValidateRstType.SEMANTIC_BUG_DIFF_DINO_STINO, '') and dpath_d_ino != dpath_st_ino:
            msg = f"d_ino and st_ino are not the same for a newly created dir:\n{op_entry.post_op_oracle.entries_path_map[dpath]}"
            log.global_logger.error(msg)
            return ValidateRstType.SEMANTIC_BUG_DIFF_DINO_STINO, msg

        # check the dir and '.' have the same ino after operations
        dotpath = dpath + '/.'
        dotpath_d_ino = op_entry.post_op_oracle.entries_path_map[dotpath].vars['Dir_Inode']
        dotpath_st_ino = op_entry.post_op_oracle.entries_path_map[dotpath].vars['File_Inode']
        if not found_key_exist(memcached_client, ValidateRstType.SEMANTIC_BUG_DIFF_DOT_INO, '') and dotpath_d_ino != dotpath_st_ino or dotpath_st_ino != dpath_d_ino:
            msg = f"dir and . have different ino for a newly created dir:\ndir attrs:\n{op_entry.post_op_oracle.entries_path_map[dpath]}\ndir's . attrs\n{op_entry.post_op_oracle.entries_path_map[dotpath]}"
            log.global_logger.error(msg)
            return ValidateRstType.SEMANTIC_BUG_DIFF_DOT_INO, msg

        # check the '..' have the same ino with its parent
        # since the parent could be the mount point, using parent's '.' file to check the ino
        dotdotpath = dotpath + '.'
        parentpath = dpath[:dpath.rfind('/')] + '/.'
        dotdot_d_ino = op_entry.post_op_oracle.entries_path_map[dotdotpath].vars['Dir_Inode']
        dotdot_st_ino = op_entry.post_op_oracle.entries_path_map[dotdotpath].vars['File_Inode']
        parent_d_ino = op_entry.post_op_oracle.entries_path_map[parentpath].vars['Dir_Inode']
        parent_st_ino = op_entry.post_op_oracle.entries_path_map[parentpath].vars['File_Inode']
        if not found_key_exist(memcached_client, ValidateRstType.SEMANTIC_BUG_DIFF_DOTDOT_INO, '') and dotdot_d_ino != dotdot_st_ino or dotdot_d_ino != parent_d_ino or dotdot_d_ino != parent_st_ino:
            msg = f"parent's . and dir's .. have different ino for a newly created dir:\ndir's .. attrs:\n{op_entry.post_op_oracle.entries_path_map[dotdotpath]}\nparent's . attrs\n{op_entry.post_op_oracle.entries_path_map[parentpath]}"
            log.global_logger.error(msg)
            return ValidateRstType.SEMANTIC_BUG_DIFF_DOTDOT_INO, msg

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_RMDIR:
        # what should be checked here
        pass

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_APPEND:
        if not found_key_exist(memcached_client, ValidateRstType.SEMANTIC_BUG_FILE_SIZE_AFTER_APPEND, ''):
            # check the file length growed by the written size (no consider of the out-of-space error)
            fpath = op_entry.post_op_oracle.fs_op.file_path
            wr_size = op_entry.post_op_oracle.fs_op.write_size
            prev_size = op_entry.prev_op_oracle.entries_path_map[fpath].vars['File_TotalSize']
            post_size = op_entry.post_op_oracle.entries_path_map[fpath].vars['File_TotalSize']
            if int(prev_size) + int(wr_size) != int(post_size):
                msg = f"incorrect file size after append, append size: {wr_size} bytes:\nprev attrs:\n{op_entry.prev_op_oracle.entries_path_map[fpath]}\npost attrs:\n{op_entry.post_op_oracle.entries_path_map[fpath]}"
                log.global_logger.error(msg)
                return ValidateRstType.SEMANTIC_BUG_FILE_SIZE_AFTER_APPEND, msg

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_WRITE:
        if not found_key_exist(memcached_client, ValidateRstType.SEMANTIC_BUG_FILE_SIZE_AFTER_WRITE, ''):
            # check the file is not less than the offset + written size (no consider of the out-of-space error)
            fpath = op_entry.post_op_oracle.fs_op.file_path
            wr_size = op_entry.post_op_oracle.fs_op.write_size
            wr_off = op_entry.post_op_oracle.fs_op.write_offset
            post_size = op_entry.post_op_oracle.entries_path_map[fpath].vars['File_TotalSize']
            if int(post_size) < int(wr_off) + int(wr_size):
                msg = f"incorrect file size after write, write offset: {wr_off}, write size: {wr_size} bytes:\nprev attrs:\n{op_entry.prev_op_oracle.entries_path_map[fpath]}\npost attrs:\n{op_entry.post_op_oracle.entries_path_map[fpath]}"
                log.global_logger.error(msg)
                return ValidateRstType.SEMANTIC_BUG_FILE_SIZE_AFTER_WRITE, msg

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_LINK:
        # what should be checked here
        pass

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_SYMLINK:
        # what should be checked here
        pass

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_RENAME:
        # what should be checked here
        pass

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_TRUNCATE:
        # what should be checked here
        pass

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_FALLOCATE:
        # what should be checked here
        pass

    elif op_entry.post_op_oracle.fs_op.type == FSOpType.OP_UMOUNT:
        # the file/dir state should not be changed after umount.
        # check if the prev and post umount state are the same.
        diff_str, diff_num = diff_ctx(op_entry.prev_op_oracle.entries_path_map, op_entry.post_op_oracle.entries_path_map, env.IGNORE_STAT_ATTR_SET())
        if diff_num != 0:
            msg = f"the file-system states before and after umount are different (- represent the prev-op state):\n{diff_str}\n"
            log.global_logger.debug(msg)
            return ValidateRstType.SEMANTIC_BUG_DIFF_STATE_BEFORE_AND_AFTER_UMOUNT, msg
        pass

    else:
        # unknown operation
        pass

    return ValidateRstType.GOOD, None

@timeit
def check_writable_thd(env : EnvBase):
    def thd_func(env : EnvBase, rst_list : list):
        # get all dir and files in the mount point
        dir_list = [env.MOD_MNT_POINT()]
        file_list = []
        for root, dirs, files in os.walk(env.MOD_MNT_POINT()):
            dir_list += [os.path.join(root, x) for x in dirs]
            file_list += [os.path.join(root, x) for x in files]

        msg = f"check_writable of {dirs}, {files}"
        log.global_logger.debug(msg)

        # generate random string, more than one block, 4177 is a prime number
        random_str = generate_random_string(4177)

        # create a new file for each dir
        count = 0
        for dpath in dir_list:
            count += 1
            fpath = f'{dpath}/file-{count}'
            try:
                with open(fpath, 'w') as fd:
                    fd.write(random_str)
            except Exception as e:
                msg = f"write {fpath} error: {e}"
                log.global_logger.error(msg)
                rst_list[0] = ValidateRstType.CANNOT_WRITE
                rst_list[1] = msg
                return 0

        # write data to each file
        for fpath in file_list:
            try:
                with open(fpath, 'a') as fd:
                    fd.write(random_str)
            except Exception as e:
                msg = f"write {fpath} error: {e}"
                log.global_logger.error(msg)
                rst_list[0] = ValidateRstType.CANNOT_WRITE
                rst_list[1] = msg
                return 0

        rst_list[0] = ValidateRstType.GOOD
        rst_list[1] = None
        return 0

    rst_list = [None, None]
    thd = threading.Thread(target=thd_func, args=(env, rst_list), daemon=True)
    thd.start()
    # timeout in 10 seconds
    thd.join(20)
    if isinstance(rst_list[0], ValidateRstType):
        return rst_list[0], rst_list[1]
    else:
        return ValidateRstType.CANNOT_WRITE, "writable check timeout"

@timeit
def check_writable(env : EnvBase):
    # get all dir and files in the mount point
    dir_list = [env.MOD_MNT_POINT()]
    file_list = []
    for root, dirs, files in os.walk(env.MOD_MNT_POINT()):
        dir_list += [os.path.join(root, x) for x in dirs]
        file_list += [os.path.join(root, x) for x in files]

    msg = f"check_writable of {dirs}, {files}"
    log.global_logger.debug(msg)

    # generate random string, more than one block, 4177 is a prime number
    random_str = generate_random_string(4177)

    # create a new file for each dir
    count = 0
    for dpath in dir_list:
        count += 1
        fpath = f'{dpath}/file-{count}'
        try:
            with open(fpath, 'w') as fd:
                fd.write(random_str)
        except Exception as e:
            msg = f"write {fpath} error: {e}"
            log.global_logger.error(msg)
            return ValidateRstType.CANNOT_WRITE, msg

    # write data to each file
    for fpath in file_list:
        try:
            with open(fpath, 'a') as fd:
                fd.write(random_str)
        except Exception as e:
            msg = f"write {fpath} error: {e}"
            log.global_logger.error(msg)
            return ValidateRstType.CANNOT_WRITE, msg

    return ValidateRstType.GOOD, None

@timeit
def check_removable(env : EnvBase):
    cmd = f'sudo rm -rf {env.MOD_MNT_POINT()}/*'
    cl_state : ShellCLState = shell_cl_local_run(cmd, 30, False)
    if cl_state.code != 0:
        return ValidateRstType.CANNOT_REMOVE, cl_state.msg()
    else:
        return ValidateRstType.GOOD, None

@timeit
def validate_crash_image_main(fs_module : ModuleDefault, env : EnvBase, memcached_client, case_dir, img : MemBinaryFile, op_entry : OpTraceEntry, op_name_list : list, op_idx : int, cp : CrashPlanEntry, cp_idx : int, dump_disk_content_to_disk : bool, dump_crash_image_to_disk : bool) -> ValidateRstType:
    rst = ValidateRstType.UNKNOWN
    other_msg = None

    clear_syslog()
    fs_module.use_raw_ko()
    img_copy = img.copy('crash plan')
    crashimage.put_cp_to_img(img_copy, op_entry, cp)

    if dump_crash_image_to_disk:
        fpath = f'{case_dir}/{op_idx:02d}-{op_entry.op_name}-{cp_idx:02d}.img'
        img_copy.dumpToFile(fpath)

    dump_img_to_dev(img_copy, env.MOD_DEV_PATH())
    if not remount_fs(fs_module):
        return ValidateRstType.REMOUNT_FAILED, None, None

    # 1. check syslog first. Met an error that the remount is okay, but loopping at get fs state.
    rst, other_msg = check_syslog()
    if rst != ValidateRstType.GOOD:
        return rst, other_msg, None

    recovery_stat : CtxFileReader = get_fs_state_thd(env.MOD_MNT_POINT(), env)
    if not recovery_stat:
        return ValidateRstType.GET_FS_STATE_FAILED, None, None

    if dump_disk_content_to_disk:
        dump_ctx_to_disk(f'{case_dir}/{op_idx:02d}-{op_entry.op_name}-{cp_idx:02d}.ctx', recovery_stat)

    found_key = None
    if cp.instruction_id > 0:
        found_key = f'{op_entry.op_name}.{cp.instruction_id}'
        # found_key = f'{op_entry.op_name}' # simplify the key to save space

    # 2. compare with prev/post-op oracle
    rst, other_msg, existing_msg = check_oracles(recovery_stat, op_entry, env)
    if rst == ValidateRstType.MISMATCH_BOTH_ORACLE:
        return rst, other_msg, existing_msg
    match_oracle_rst = rst
    rst = ValidateRstType.GOOD # reset the type

    # 3. check vfs semantic
    rst, other_msg = check_fs_semantic(memcached_client, op_entry, env)
    if rst != ValidateRstType.GOOD:
        found_key_insert(memcached_client, rst, '')
        return rst, other_msg, None

    # 4. check subsequent operations
    # 4.1 readable
    # it is unnecessary to check readable, since when getting fs stat, all directories and files are read.

    # 4.2 writable
    if not found_key or not found_key_exist(memcached_client, ValidateRstType.CANNOT_WRITE, found_key):
        rst, other_msg = check_writable_thd(env)
        if rst != ValidateRstType.GOOD:
            return rst, other_msg, other_msg

    # 4.3 removable
    if not found_key or not found_key_exist(memcached_client, ValidateRstType.CANNOT_REMOVE, found_key):
        rst, other_msg = check_removable(env)
        if rst != ValidateRstType.GOOD:
            return rst, other_msg, other_msg

    # 5. check the recovered content
    match_content_rst = ValidateRstType.GOOD
    if match_oracle_rst == ValidateRstType.MATCH_PREV_ORACLE:
        match_content_rst, other_msg = check_recovered_content(memcached_client, env, op_entry, cp, check_old_value=True)
    elif match_oracle_rst == ValidateRstType.MATCH_POST_ORACLE:
        match_content_rst, other_msg = check_recovered_content(memcached_client, env, op_entry, cp, check_new_value=True)
    else:
        # impossible
        pass

    # 6. umount
    if not unmount_fs(fs_module):
        return ValidateRstType.UMOUNT_FAILED, None

    # check the content comparison result after umount, since it is the least important checks in sometimes.
    if match_content_rst != ValidateRstType.GOOD:
        # find the location and variable in the msg
        var_info = 'var_not_found'
        if other_msg and other_msg.find('vars:') > 0 and other_msg.find('call path:') > 0:
            var_info = other_msg[other_msg.find('vars:'):other_msg.find('call path:')]
        return match_content_rst, other_msg, var_info

    return ValidateRstType.GOOD, None, None

@timeit
def validate_crash_image(fs_module : ModuleDefault, env : EnvBase, memcached_client, case_dir, img : MemBinaryFile, op_entry : OpTraceEntry, op_name_list : list, op_idx : int, cp : CrashPlanEntry, total_cps : int, cp_idx : int, dump_disk_content_to_disk : bool, dump_crash_image_to_disk : bool):
    rst, other_msg, existkey_msg = validate_crash_image_main(fs_module, env, memcached_client, case_dir, img, op_entry, op_name_list, op_idx, cp, cp_idx, dump_disk_content_to_disk, dump_crash_image_to_disk)
    if rst != ValidateRstType.GOOD:
        add_cp_and_validate_rst_to_mc(memcached_client, case_dir, op_name_list, op_idx, total_cps, cp_idx, rst)
        # remove module if not removed
        if rst != ValidateRstType.UMOUNT_FAILED and rst != ValidateRstType.MISMATCH_OLD_VALUE and rst != ValidateRstType.MISMATCH_NEW_VALUE:
            unmount_fs(fs_module)
        proc_validate_result(rst, memcached_client, case_dir, op_entry, op_name_list, cp, other_msg, existkey_msg)
