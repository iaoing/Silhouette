import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase
from scripts.fs_conf.base.module_base import ModuleBase
from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.shell_wrap.shell_ssh_run import shell_cl_ssh_run
from scripts.shell_wrap.shell_cl_state import ShellCLState
from scripts.utils.logger import global_logger

class ModuleDefault(ModuleBase):
    """docstring for ModuleDefault."""
    def __init__(self, env : EnvBase, ssh_alias_name, local_run : bool):
        self.name = env.MODULE_NAME()
        self.llvm15_home = env.GUEST_LLVM15_HOME()
        self.src_dir = env.FS_MODULE_SRC_DIR()
        self.build_dir = env.MODULE_MAKE_DIR()
        self.trace_src = env.RUNTIME_TRACE_SRC()
        self.info_exe = env.INFO_DUMP_EXE()
        self.info_struct = env.INFO_STRUCT_FNAME()
        self.info_posix = env.INFO_POSIX_FN_FNAME()
        self.info_trace = env.INFO_TRACE_FN_FNAME()
        self.struct_layout_exe = env.STRUCT_LAYOUT_EXE()
        self.struct_layout_fname = env.STRUCT_LAYOUT_FNAME()
        self.instid_srcloc_map_fpath = env.INSTID_SRCLOC_MAP_FPATH()
        self.mod_name = env.MODULE_NAME()
        self.insert_para = env.MOD_INS_PARA()
        self.dev_path = env.MOD_DEV_PATH()
        self.mnt_type = env.MOD_MNT_TYPE()
        self.mnt_para = env.MOD_MNT_PARA()
        self.remnt_para = env.MOD_REMNT_PARA()
        self.mnt_point = env.MOD_MNT_POINT()
        self.user_name = env.GUEST_USERNAME()
        self.guest_name = ssh_alias_name
        self.local_run = local_run

        self.fs_instrumented_ko = "/home/%s/fs_instrumented.ko" % (self.user_name)
        self.fs_raw_ko = "/home/%s/fs_raw.ko" % (self.user_name)
        self.target_ko = "%s/%s.ko" % (self.src_dir, self.mod_name)

        self.makefile_vars = "LLVM15_HOME=%s " % (self.llvm15_home) + \
                "MODULE_NAME=%s " % (self.mod_name) + \
                "FS_MODULE_SRC_DIR=%s " % (self.src_dir) + \
                "RUNTIME_TRACE_SRC=%s " % (self.trace_src) + \
                "INFO_DUMP_EXE=%s " % (self.info_exe) + \
                "INFO_STRUCT_FNAME=%s " % (self.info_struct) + \
                "INFO_POSIX_FN_FNAME=%s " % (self.info_posix) + \
                "INFO_TRACE_FN_FNAME=%s " % (self.info_trace) + \
                "STRUCT_LAYOUT_EXE=%s " % (self.struct_layout_exe) + \
                "STRUCT_LAYOUT_FNAME=%s " % (self.struct_layout_fname) + \
                "INSTID_SRCLOC_MAP_FPATH=%s " % (self.instid_srcloc_map_fpath)

    def cmd_agent(self, cmd, host_name, ttl, crash_on_err=False):
        if self.local_run:
            return shell_cl_local_run(cmd, ttl=ttl, crash_on_err=crash_on_err)
        else:
            return shell_cl_ssh_run(cmd, host_name, ttl=ttl, crash_on_err=crash_on_err)

    def build_raw_kobj(self):
        '''build raw object'''
        cmd = "make -C %s %s raw_ko" % (self.build_dir, self.makefile_vars)

        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_BUILD_RAW)

        if cl_state.code != 0:
            err_msg = "build raw %s failed, %s" % (self.name, cl_state.msg())
            global_logger.error(err_msg)
            assert False, err_msg

        cmd = "cp %s/%s.ko %s" % (self.src_dir, self.mod_name, self.fs_raw_ko)
        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_BUILD_INST)
        if cl_state.code != 0:
            err_msg = "copy instrumented ko %s failed, %s" % (self.name, cl_state.msg())
            global_logger.error(err_msg)
            assert False, err_msg

        return cl_state.code == 0

    def build_instrument_kobj(self):
        '''build instrument object'''
        # make clean first
        cmd = "make -C %s clean" % (self.build_dir)
        cl_state : ShellCLState = None
        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_BUILD_INST)
        if cl_state.code != 0:
            err_msg = "make build dir clean %s failed, %s" % (self.name, cl_state.msg())
            global_logger.error(err_msg)
            assert False, err_msg

        cmd = "make -C %s clean" % (self.src_dir)
        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_BUILD_INST)
        if cl_state.code != 0:
            err_msg = "make fs module src dir clean %s failed, %s" % (self.name, cl_state.msg())
            global_logger.error(err_msg)
            assert False, err_msg

        cmd = "make -C %s %s inst_ko" % (self.build_dir, self.makefile_vars)
        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_BUILD_INST)
        if cl_state.code != 0:
            err_msg = "build instrumented %s failed, %s" % (self.name, cl_state.msg())
            global_logger.error(err_msg)
            assert False, err_msg

        cmd = "cp %s/%s.ko %s" % (self.src_dir, self.mod_name, self.fs_instrumented_ko)
        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_BUILD_INST)
        if cl_state.code != 0:
            err_msg = "copy instrumented ko %s failed, %s" % (self.name, cl_state.msg())
            global_logger.error(err_msg)
            assert False, err_msg

        return cl_state.code == 0

    def use_instrumented_ko(self):
        self.target_ko = self.fs_instrumented_ko

    def use_raw_ko(self):
        self.target_ko = self.fs_raw_ko

    def insert_module(self):
        '''insert FS module'''
        cmd = "sudo insmod %s %s" % (self.target_ko, self.insert_para)

        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_INSMOD)

        if cl_state.code != 0:
            log_msg = "insert module %s failed, %s" % (self.name, cl_state.msg())
            global_logger.warning(log_msg)
            # we do not crash at here, since unexpected situations (kernel panic) can cause the insert fault.

        return cl_state.code == 0

    def remove_module(self):
        '''remove FS module'''
        cmd = "sudo rmmod %s" % (self.mod_name)

        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_RMMOD)

        if cl_state.code != 0:
            log_msg = "remove module %s failed, %s" % (self.name, cl_state.msg())
            global_logger.warning(log_msg)
            # we do not crash at here, since unexpected situations (kernel panic) can cause the insert fault.

        return cl_state.code == 0

    def mount_fs(self):
        '''mount FS'''
        cmd = "sudo mount -t %s -o %s %s %s" % (self.mnt_type, self.mnt_para, self.dev_path, self.mnt_point)

        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_MOUNT)

        if cl_state.code != 0:
            log_msg = "mount %s failed, %s" % (self.name, cl_state.msg())
            global_logger.warning(log_msg)
            # we do not crash at here, since unexpected situations (kernel panic) can cause the insert fault.

        return cl_state.code == 0

    def remount_fs(self):
        '''mount FS'''
        cmd = "sudo mount -t %s -o %s %s %s" % (self.mnt_type, self.remnt_para, self.dev_path, self.mnt_point)

        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_MOUNT)

        if cl_state.code != 0:
            log_msg = "remount %s failed, %s" % (self.name, cl_state.msg())
            global_logger.warning(log_msg)
            # we do not crash at here, since unexpected situations (kernel panic) can cause the insert fault.

        return cl_state.code == 0

    def chown_mnt_point(self):
        '''change the ownship of the mnt point'''
        cmd = "sudo chown -R %s:%s %s" % (self.user_name, self.user_name, self.mnt_point)

        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_MOUNT)

        if cl_state.code != 0:
            log_msg = "chown %s failed, %s" % (self.name, cl_state.msg())
            global_logger.warning(log_msg)
            # we do not crash at here, since unexpected situations (kernel panic) can cause the insert fault.

        return cl_state.code == 0

    def unmount_fs(self):
        '''unmount FS'''
        cmd = "sudo umount %s" % (self.mnt_point)

        cl_state = self.cmd_agent(cmd, self.guest_name, ttl=super().TTL_MOUNT)

        if cl_state.code != 0:
            log_msg = "umount %s failed, %s" % (self.name, cl_state.msg())
            global_logger.warning(log_msg)
            # we do not crash at here, since unexpected situations (kernel panic) can cause the insert fault.

        return cl_state.code == 0

