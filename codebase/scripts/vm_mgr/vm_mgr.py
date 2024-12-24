import os
import sys
import time
import multiprocessing

codebase_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger
import scripts.utils.utils as my_utils
import scripts.utils.const_var as my_const
from scripts.fs_conf.base.env_base import EnvBase
from scripts.vm_mgr.socket_port import find_first_available_port
from scripts.vm_mgr.vm_instance import VMInstance
from scripts.vm_mgr.vm_config import VMConfig
from scripts.vm_mgr.ssh_config import SSHConfigPool

class VMMgr:
    """
    VMMgr is the base VM which can be used to generate other derived VMs.
    VMMgr only manage VMs which is derived from it.
    """
    def __init__(self, env : EnvBase, ssh_config_pool: SSHConfigPool, base_img_file = None):
        self.run_limit = env.RUN_LIMIT()
        self.img_file = env.BASE_IMG_FILE()
        self.num_cpu = env.NUM_CPU()
        self.mem_size_gb = env.MEM_SIZE_GB()
        self.pm_file = env.BASE_PM_FILE()
        self.pm_size_mb = env.PM_SIZE_MB()
        self.dram_emulate_pm = env.DRAM_EMUILATED_PM_DEV()
        self.ssh_config_pool = ssh_config_pool

        if base_img_file:
            self.img_file = base_img_file

        # the number should not exceed the number of cores.
        if self.run_limit <= 0 or self.run_limit >= multiprocessing.cpu_count():
            self.run_limit = multiprocessing.cpu_count() - 1
        if self.run_limit == 0:
            self.run_limit = 1
        global_logger.info("run limit: %d" % (self.run_limit))

        # vnc number for each vm instance
        self.vnc_num_list = list(range(10, self.run_limit + 10))
        global_logger.debug("vnc number list: %s" % (str(self.vnc_num_list)))

        # we need a base vm that all other vms should be created based on it.
        # base vm does not create a vm instance, such we do not need a real vnc number for it
        self.base_vm_config = VMConfig(
            "base", self.num_cpu, self.mem_size_gb, self.pm_file, self.pm_size_mb, self.img_file, -1, -1, self.dram_emulate_pm)
        global_logger.debug("base vm config, %s" % (self.base_vm_config))

        # all created vm instances, no matter running or not started yet.
        self.live_vm_instances = []
        # if the vm is finished, killed, or terminated, move it to this list
        self.dead_vm_instances = []
        # reclaimed resource from vm in dead vm instance list
        # ssh config will be reclaimed when moving to this list
        self.reclaimed_vm_instances = []

    def has_enough_space(self, check_img_dev=True, check_pm_dev=True) -> bool:
        '''Check if the disk has enough space for new VM image'''
        ret = True
        if check_img_dev and my_utils.getMountPointFreeSpaceSizeGiB(self.base_vm_config.img_file) < my_const.MIN_IMG_DEV_SPACE:
            ret = False
            err_msg = "no enough space in %s, %dGiB, should have %dGiB" % (
                self.base_vm_config.img_file, my_utils.getMountPointFreeSpaceSizeGiB(self.base_vm_config.img_file), my_const.MIN_IMG_DEV_SPACE)
            global_logger.error(err_msg)
        if not self.dram_emulate_pm and check_pm_dev and my_utils.getMountPointFreeSpaceSizeGiB(self.base_vm_config.pm_file) < my_const.MIN_PM_DEV_SPACE:
            err_msg = "no enough space in %s, %dGiB, should have %dGiB" % (
                self.base_vm_config.pm_file, my_utils.getMountPointFreeSpaceSizeGiB(self.base_vm_config.pm_file), my_const.MIN_PM_DEV_SPACE)
            global_logger.error(err_msg)
            ret = False
        return ret

    def exceed_run_limit(self):
        return len(self.live_vm_instances) >= self.run_limit

    def create_vm(self, vm_file_name=None, pm_file_name=None, father_config=None) -> VMInstance:
        if self.exceed_run_limit():
            self.search_dead_vm()

        if self.exceed_run_limit():
            return False, 'exceed_run_limit'

        if not self.has_enough_space():
            if not self.reclaim_resource():
                err_msg = "no dead resource can be reclaimed"
                global_logger.error(err_msg)
                assert False, err_msg

        # sleep 1 second to avoid conflict of timestamp
        time.sleep(1)
        timestamp = my_utils.getTimestampPureNum()

        if father_config == None:
            father_config = self.base_vm_config

        global_logger.debug("father vm config: %s" % (str(father_config)))
        if vm_file_name == None:
            last_dot_pos = self.base_vm_config.img_file.rfind(".")
            assert last_dot_pos >= 0
            vm_file_name = self.base_vm_config.img_file[:last_dot_pos] + "." + str(
                timestamp) + ".qcow2"

        if pm_file_name == None:
            pm_file_name = self.base_vm_config.pm_file + "." + str(timestamp)

        ssh_config = self.ssh_config_pool.alloc_ssh_config()
        if not ssh_config:
            err_msg = "allocate ssh config failed"
            global_logger.error(err_msg)
            assert False, err_msg

        assert len(
            self.vnc_num_list) > 0, "vnc number does not match the number of living vm instance"

        vm_config = VMConfig(timestamp, father_config.num_cpu,
                             father_config.mem_size_gb,
                             pm_file_name, father_config.pm_size_mb,
                             vm_file_name, self.vnc_num_list[0], ssh_config.port, self.dram_emulate_pm)
        self.vnc_num_list.pop(0)
        global_logger.debug("vm config: %s" % (str(vm_config)))

        vm_instance = VMInstance(ssh_config, vm_config, father_config)

        if not vm_instance.init():
            if self.has_enough_space():
                # if this is not the space issue, assert here.
                err_msg = "vm instance init failed, not space issue"
                global_logger.critical(err_msg)
                assert False, err_msg

            # space is not enough, call make space might solve this problem.
            log_msg = "no enough space to create files for vm, %s" % (
                str(vm_config))
            global_logger.error(log_msg)
            assert False, log_msg

            del vm_instance
            self.ssh_config_pool.dealloc_ssh_config(ssh_config)
            return None

        self.live_vm_instances.append(vm_instance)
        return vm_instance

    def search_dead_vm(self):
        new_list = []
        for vm in self.live_vm_instances:
            vm: VMInstance
            if vm.is_started() and not vm.is_running():
                self.dead_vm_instances.append(vm)
                self.vnc_num_list.append(vm.vm_config.vnc_num)
                assert len(self.vnc_num_list) == len(set(self.vnc_num_list)), \
                    "has duplicates in vnc list, %s" % (str(self.vnc_num_list))
            else:
                new_list.append(vm)
        self.live_vm_instances = new_list

    def reclaim_resource(self, vm: VMInstance = None):
        '''
        reclaim resource from the dead vm if mv is not provided.
        returns true if been reclaimed, otherwise false
        '''
        if not vm:
            self.search_dead_vm()
            if len(self.dead_vm_instances) == 0:
                return False
            else:
                vm = self.dead_vm_instances[0]

        if not vm.destory_resource(vm_file=True, pm_file=True):
            err_msg = "reclaim resource from vm %s failed" % (str(vm))
            global_logger.error(err_msg)
            assert False, err_msg

        self.ssh_config_pool.dealloc_ssh_config(vm.ssh_config)
        log_msg = "deallocate ssh config, %s" % (vm.ssh_config)
        global_logger.debug(log_msg)

        self.dead_vm_instances.remove(vm)

        self.reclaimed_vm_instances.append(vm)
        return True

    def kill_all_vm(self):
        for vm in self.live_vm_instances:
            vm: VMInstance
            if vm.is_running():
                if not vm.kill():
                    err_msg = "kill vm failed, %s" % (str(vm))
                    global_logger.error(err_msg)
                    assert False, err_msg
            self.dead_vm_instances.append(vm)
            self.vnc_num_list.append(vm.vm_config.vnc_num)
            assert len(self.vnc_num_list) == len(set(self.vnc_num_list)), \
                "has duplicates in vnc list, %s" % (str(self.vnc_num_list))

        self.live_vm_instances.clear()
        assert len(self.vnc_num_list) == self.run_limit, \
            "len of vnc list does not match the run list, %d, %s" % (
                self.run_limit, str(self.vnc_num_list))

    def destory_all_vm(self):
        while len(self.dead_vm_instances) > 0:
            self.reclaim_resource()

    def destory(self):
        self.kill_all_vm()
        self.destory_all_vm()
