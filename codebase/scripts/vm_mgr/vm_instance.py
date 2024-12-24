import os
import sys
import time
import asyncio
from qemu.qmp import QMPClient
from copy import deepcopy

codebase_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

import scripts.utils.logger as log
from scripts.utils.proc_state import is_process_running
import scripts.utils.utils as my_utils
import scripts.utils.const_var as my_const
from scripts.vm_mgr.ssh_config import SSHConfig
from scripts.vm_mgr.ssh_config import SSHConfigPool
from scripts.vm_mgr.vm_config import VMConfig
import scripts.shell_wrap.shell_cmd_helper as shell_cmd_helper
from scripts.shell_wrap.shell_ssh_run import shell_cl_ssh_run
from scripts.shell_wrap.shell_local_run import shell_cl_local_run

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.host.vm_instance.{func.__name__}:{time.perf_counter() - start_time}")
        return result
    return wrapper

class VMInstance:
    """
    docstring for VMInstance.
    qemu-system-x86_64 -machine pc-q35-focal,accel=kvm,nvdimm=on \
        -cpu host -smp cpus=1 -m 8G,slots=8,maxmem=64G -enable-kvm \
        -object memory-backend-file,id=mem1,share=on,mem-path=/mnt/pmem0/qemu/nvdimm.32m.img,size=32M \
        -device nvdimm,id=nvdimm,memdev=mem1 \
        -drive file=/path/to/qemu/img/xxx.qcow2,format=qcow2,index=0,media=disk \
        -boot once=c \
        -vnc :0 -net nic -net user,hostfwd=tcp::2222-:22 -daemonize
    """
    QEMU_BASE_CMD_WITH_PM_FILE = 'qemu-system-x86_64 -machine pc-q35-focal,accel=kvm,nvdimm=on ' \
        '-cpu host -smp cpus=NUMCPU -m MEMSIZE,slots=4,maxmem=64G -enable-kvm ' \
        '-object memory-backend-file,id=MEMDEVID,share=off,mem-path=PMDEVFILE,size=PMDEVSIZE ' \
        '-device nvdimm,id=nvdimm,memdev=MEMDEVID ' \
        '-drive file=QCOW2FILE,format=qcow2,index=0,media=disk ' \
        '-boot once=c ' \
        '-vnc :VNCNUM -net nic -net user,hostfwd=tcp::PORTNUM-:22 -daemonize '\
        '-qmp unix:VMMONSOCKET,server,nowait'

    QEMU_BASE_CMD_WITH_DRAM_EMULATED_PM = 'qemu-system-x86_64 -machine pc-q35-focal,accel=kvm,nvdimm=on ' \
        '-cpu host -smp cpus=NUMCPU -m MEMSIZE,slots=4,maxmem=64G -enable-kvm ' \
        '-drive file=QCOW2FILE,format=qcow2,index=0,media=disk ' \
        '-boot once=c ' \
        '-vnc :VNCNUM -net nic -net user,hostfwd=tcp::PORTNUM-:22 -daemonize '\
        '-qmp unix:VMMONSOCKET,server,nowait'

    def __init__(self, ssh_config: SSHConfig, vm_config: VMConfig, vm_parent: VMConfig):
        self.ssh_config = deepcopy(ssh_config)
        self.vm_config = deepcopy(vm_config)
        self.vm_parent = deepcopy(vm_parent)

        self.vm_proc = None
        self.start_cmd = None

    def init(self) -> bool:
        # create the current vm image based on the father's image
        if not self.__create_image():
            log.global_logger.error("__create_image failed")
            return False
        # backup the new created image file in case of lost
        if not self.__backup_img_file():
            log.global_logger.error("__backup_img_file failed")
            return False
        # create required files, e.g., the pm file, the dev file
        if not self.vm_config.dram_emulate_pm:
            if not self.__create_pm_file():
                log.global_logger.error("__create_pm_file failed")
                return False

        # the start_cmd to start the vm
        self.__init_vm_start_cmd(self.ssh_config, self.vm_config)

        return True

    def __create_image(self):
        if not my_utils.fileExists(self.vm_parent.img_file):
            err_msg = "the vm father's image does not exist, %s" % (
                str(self.vm_parent))
            assert False, err_msg

        if my_utils.fileExists(self.vm_config.img_file):
            log.global_logger.warning("the vm image exists, %s" %
                                  (str(self.vm_config)))
            if is_process_running(key_word=self.vm_config.img_file):
                err_msg = "the vm is running now, %s" % ((str(self.vm_config)))
                assert False, err_msg
            else:
                log.global_logger.debug(
                    "going to delete the vm file, %s" % ((str(self.vm_config))))
                if not my_utils.removeFile(self.vm_config.img_file):
                    err_msg = "cannot remove the vm file, %s" % (
                        self.vm_config.img_file)
                    assert False, err_msg

        cmd = 'qemu-img create -f qcow2 -b %s -F qcow2 %s' % (
            self.vm_parent.img_file, self.vm_config.img_file)
        ret = shell_cl_local_run(cmd, crash_on_err=True)
        if ret.code != 0:
            err_msg = "create qcow2 image file failed %s %s" % (
                self.vm_parent.img_file, self.vm_config.img_file)
            log.global_logger.error(err_msg)
            assert False, err_msg

        return True

    @classmethod
    def get_backup_img_fname(cls, fname):
        bak_fname = fname + ".bak"
        return bak_fname

    def __backup_img_file(self):
        bak_fname = self.get_backup_img_fname(self.vm_config.img_file)
        if not my_utils.copyFile(self.vm_config.img_file, bak_fname):
            err_msg = "backup img file failed %s %s" % (
                self.vm_config.img_file, bak_fname)
            log.global_logger.error(err_msg)
            assert False, err_msg
        return True

    def __create_pm_file(self):
        if my_utils.fileExists(self.vm_config.pm_file):
            log_msg = "the vm's pm file exists, %s" % (str(self.vm_config))
            log.global_logger.warning(log_msg)
            if is_process_running(key_word=self.vm_config.pm_file):
                err_msg = "the vm's pm file is in using, %s" % (
                    (str(self.vm_config)))
                assert False, err_msg
            else:
                log.global_logger.debug(
                    "going to delete the vm's pm file, %s" % ((str(self.vm_config))))
                if not my_utils.removeFile(self.vm_config.pm_file):
                    err_msg = "cannot remove the vm file, %s" % (
                        self.vm_config.pm_file)
                    assert False, err_msg

        log_msg = "create file %s with length %d MiB" % (
            self.vm_config.pm_file, self.vm_config.pm_size_mb)
        log.global_logger.debug(log_msg)
        if not my_utils.createFile(self.vm_config.pm_file, self.vm_config.pm_size_mb * 1048576):
            err_msg = "create pm file failed %s with size %d MiB" % (
                self.vm_config.pm_file, self.vm_config.pm_size_mb)
            log.global_logger.error(err_msg)
            # this may because of the run out of space, thus we return false instead of crash
            return False
        return True

    def __init_vm_start_cmd(self, ssh_config: SSHConfig, vm_config: VMConfig):
        if self.vm_config.dram_emulate_pm:
            self.start_cmd = str(self.QEMU_BASE_CMD_WITH_DRAM_EMULATED_PM)
            self.start_cmd = self.start_cmd.replace(
                "NUMCPU", "%d" % (vm_config.num_cpu))
            self.start_cmd = self.start_cmd.replace(
                "MEMSIZE", "%dG" % (vm_config.mem_size_gb))
            self.start_cmd = self.start_cmd.replace(
                "QCOW2FILE", "%s" % (vm_config.img_file))
            self.start_cmd = self.start_cmd.replace(
                "PORTNUM", "%d" % (ssh_config.port))
            self.start_cmd = self.start_cmd.replace(
                "VNCNUM", "%d" % (vm_config.vnc_num))
            self.start_cmd = self.start_cmd.replace(
                "VMMONSOCKET", self.get_vm_mon_socket_fpath())
        else:
            self.start_cmd = str(self.QEMU_BASE_CMD_WITH_PM_FILE)
            self.start_cmd = self.start_cmd.replace(
                "NUMCPU", "%d" % (vm_config.num_cpu))
            self.start_cmd = self.start_cmd.replace(
                "MEMSIZE", "%dG" % (vm_config.mem_size_gb))
            self.start_cmd = self.start_cmd.replace(
                "MEMDEVID", "mem%s" % (vm_config.str_id))
            self.start_cmd = self.start_cmd.replace(
                "PMDEVFILE", "%s" % (vm_config.pm_file))
            self.start_cmd = self.start_cmd.replace(
                "PMDEVSIZE", "%dM" % (vm_config.pm_size_mb))
            self.start_cmd = self.start_cmd.replace(
                "QCOW2FILE", "%s" % (vm_config.img_file))
            self.start_cmd = self.start_cmd.replace(
                "PORTNUM", "%d" % (ssh_config.port))
            self.start_cmd = self.start_cmd.replace(
                "VNCNUM", "%d" % (vm_config.vnc_num))
            self.start_cmd = self.start_cmd.replace(
                "VMMONSOCKET", self.get_vm_mon_socket_fpath())

    def get_host_name(self):
        return self.ssh_config.alias_name

    def get_vm_mon_socket_fpath(self):
        return f'/tmp/qemu_vm{self.ssh_config.port}.sock'

    def start(self) -> bool:
        self.vm_proc = shell_cl_local_run(self.start_cmd)
        return (self.vm_proc.code == 0)

    def is_started(self) -> bool:
        return self.vm_proc != None

    def is_running(self) -> bool:
        return self.is_started() and  \
            self.vm_proc.is_vm_running(key=self.vm_config.img_file)

    def terminal(self, ttw=60) -> bool:
        if not self.is_running():
            return True

        key = self.vm_config.img_file
        cmd = "sudo shutdown -h now"
        cl_state = shell_cl_ssh_run(cmd, self.ssh_config.alias_name)
        log.global_logger.debug("%s" % (cl_state.msg()))

        while ttw >= 0:
            if self.is_running():
                ttw -= 5
                time.sleep(5)
            else:
                break
        return not self.is_running()

    def kill(self) -> bool:
        if not self.is_running():
            log_msg = "VM is not running: %s" % (str(self.vm_config))
            log.global_logger.debug(log_msg)
            return True
        return self.vm_proc.kill_vm(key=self.vm_config.img_file)

    def access_ok(self) -> bool:
        cmd = shell_cmd_helper.shell_cl_true()
        host_name = self.get_host_name()
        cl_state = shell_cl_ssh_run(
            cmd, host_name, ttl=my_const.TTL_VM_ACCESS_OK)
        return (cl_state.code == 0)

    async def _qmp_status_running(self, vm_tag):
        ret = False

        qmp = QMPClient(self.ssh_config.alias_name)
        await qmp.connect(self.get_vm_mon_socket_fpath())

        res = await qmp.execute('query-status')
        msg = f'savevm ret: {res}'
        log.global_logger.debug(msg)

        if 'status' in res and 'running' in res['status']:
            ret = True

        await qmp.disconnect()

        return ret

    def qmp_status_running(self, vm_tag='checkpoint_default'):
        return asyncio.run(self._qmp_status_running(vm_tag))

    async def _create_snapshot(self, vm_tag):
        qmp = QMPClient(self.ssh_config.alias_name)
        await qmp.connect(self.get_vm_mon_socket_fpath())

        res = await qmp.execute('human-monitor-command', {'command-line': f'savevm {vm_tag}'})
        msg = f'savevm ret: {res}'
        log.global_logger.debug(msg)

        await qmp.disconnect()

    @timeit
    def create_snapshot(self, vm_tag='checkpoint_default', wait=True):
        asyncio.run(self._create_snapshot(vm_tag))

    async def _restore_snapshot(self, vm_tag) -> bool:
        qmp = QMPClient(self.ssh_config.alias_name)
        await qmp.connect(self.get_vm_mon_socket_fpath())

        res = await qmp.execute('human-monitor-command', {'command-line': f'loadvm {vm_tag}'})
        msg = f'loadvm ret: {res}'
        log.global_logger.debug(msg)

        await qmp.disconnect()

    @timeit
    def restore_snapshot(self, vm_tag='checkpoint_default') -> bool:
        asyncio.run(self._restore_snapshot(vm_tag))

    def restore_snapshot_until_access(self, retry_time=1):
        # it unnecessary to check access since we wait until restoring is complete.
        ret = False
        while retry_time > 0:
            self.restore_snapshot()
            if self.wait_until_access_ok():
                ret = True
                break
        return ret

    def restart_if_cannot_access(self, retry_time=1, force=False) -> bool:
        if not force and self.access_ok():
            return True

        kill_retry = 5
        if force:
            while kill_retry > 0 and self.is_running():
                self.kill()
                kill_retry -= 1
            if self.is_running():
                err_msg = "cannot kill the vm, %s, %s" % (
                    self.ssh_config.__str__(), self.vm_config.__str__())
                log.global_logger.error(err_msg)
                assert False, err_msg

        ret = False
        while retry_time > 0 and not self.access_ok():
            retry_time -= 1
            self.start()
            if self.wait_until_access_ok():
                ret = True
                break
        return ret

    def get_ssh_cmd_header(self):
        return "ssh %s " % (self.ssh_config.alias_name)

    def wait_until_access_ok(self, ttw=120) -> bool:
        if not self.is_running():
            return False

        while ttw > 0:
            if self.access_ok():
                return True
            else:
                ttw -= 5
                time.sleep(5)
        return self.access_ok()

    def destory_resource(self, vm_file=False, pm_file=False) -> bool:
        '''
        return false if vm is running
        assert if file exist but cannot be deleted
        '''
        if self.is_running():
            log_msg = "VM is running, cannot destory resource, %s" % (
                str(self.vm_config))
            log.global_logger.warning(log_msg)
            return False

        if vm_file:
            if my_utils.fileExists(self.vm_config.img_file):
                if not my_utils.removeFile(self.vm_config.img_file):
                    err_msg = "remove file %s failed" % (
                        self.vm_config.img_file)
                    log.global_logger.error(err_msg)
                    assert False, err_msg
            else:
                log_msg = "image file does not exist, %s" % (
                    self.vm_config.img_file)
                log.global_logger.warning(log_msg)

            bak_fname = self.get_backup_img_fname(self.vm_config.img_file)
            if my_utils.fileExists(bak_fname):
                if not my_utils.removeFile(bak_fname):
                    err_msg = "remove backup file %s failed" % (bak_fname)
                    log.global_logger.error(err_msg)
                    assert False, err_msg
            else:
                log_msg = "image bak file does not exist, %s" % (bak_fname)
                log.global_logger.warning(log_msg)

        if pm_file:
            if self.vm_config.dram_emulate_pm:
                pass
            elif my_utils.fileExists(self.vm_config.pm_file):
                if not my_utils.removeFile(self.vm_config.pm_file):
                    err_msg = "remove file %s failed" % (
                        self.vm_config.pm_file)
                    log.global_logger.error(err_msg)
                    assert False, err_msg
            else:
                log_msg = "pm file does not exist, %s" % (
                    self.vm_config.pm_file)
                log.global_logger.warning(log_msg)

        return True
