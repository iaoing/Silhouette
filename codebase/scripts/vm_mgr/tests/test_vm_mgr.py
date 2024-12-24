import os
import sys
import unittest
import shutil
import logging
import time

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

import scripts.utils.utils as my_utils
from scripts.utils.logger import setup_global_logger
from scripts.fs_conf.base.env_base import EnvBase
from scripts.vm_mgr.ssh_config import SSHConfig
from scripts.vm_mgr.ssh_config import SSHConfigPool
from scripts.vm_mgr.vm_config import VMConfig
from scripts.vm_mgr.vm_instance import VMInstance
from scripts.vm_mgr.vm_mgr import VMMgr

class EnvTest(EnvBase):
    def __init__(self):
        pass

    def MODULE_NAME(self) -> str:
        pass

    def FS_MODULE_SRC_DIR(self) -> str:
        pass

    def MOD_INS_PARA(self) -> str:
        pass

    def MOD_MNT_TYPE(self) -> str:
        pass

    def MOD_MNT_PARA(self) -> str:
        pass

    def MOD_REMNT_PARA(self) -> str:
        pass

class TestVMInstance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_global_logger(fname="xx.xx", file_lv=logging.DEBUG, stm=sys.stderr, stm_lv=logging.ERROR)

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self) -> None:
        self.env = EnvTest()
        self.ssh_config_pool = SSHConfigPool(self.env)
        self.vm_mgr = VMMgr(self.env, self.ssh_config_pool)

    def tearDown(self) -> None:
        self.vm_mgr.destory()
        self.ssh_config_pool.destory_pool()

    def test_setup_and_teardown(self):
        self.assertEqual(len(self.vm_mgr.live_vm_instances), 0)
        self.assertEqual(len(self.vm_mgr.dead_vm_instances), 0)
        self.assertEqual(len(self.vm_mgr.reclaimed_vm_instances), 0)

    def test_exceed_run_limit(self):
        ret = self.vm_mgr.exceed_run_limit()
        self.assertFalse(ret)

        run_limit = self.vm_mgr.run_limit
        self.vm_mgr.run_limit = 0
        ret = self.vm_mgr.exceed_run_limit()
        self.assertTrue(ret)

        ret = self.vm_mgr.create_vm()
        self.assertFalse(ret)

        self.vm_mgr.run_limit = run_limit

    def test_create_vm(self):
        vm = self.vm_mgr.create_vm()
        vm : VMInstance
        self.assertTrue(vm)

        ret = vm.init()
        self.assertTrue(ret)
        self.assertTrue(my_utils.fileExists(vm.vm_config.img_file))
        self.assertTrue(my_utils.fileExists(vm.vm_config.pm_file))

        self.assertFalse(vm.is_started())
        self.assertFalse(vm.is_running())
        self.assertTrue(vm.terminal())
        self.assertTrue(vm.kill())

    def test_run_vm_1(self):
        vm = self.vm_mgr.create_vm()
        vm : VMInstance
        self.assertTrue(vm)

        ret = vm.init()
        self.assertTrue(ret)
        self.assertTrue(my_utils.fileExists(vm.vm_config.img_file))
        self.assertTrue(my_utils.fileExists(vm.vm_config.pm_file))

        self.assertFalse(vm.is_started())
        self.assertFalse(vm.is_running())
        self.assertTrue(vm.terminal())
        self.assertTrue(vm.kill())

        # run vm instance
        ret = vm.start()
        self.assertTrue(ret)

    def test_run_vm_2(self):
        # vm 1
        vm1 = self.vm_mgr.create_vm()
        vm1 : VMInstance
        self.assertTrue(vm1)
        ret = vm1.init()
        self.assertTrue(ret)
        self.assertTrue(my_utils.fileExists(vm1.vm_config.img_file))
        self.assertTrue(my_utils.fileExists(vm1.vm_config.pm_file))
        self.assertFalse(vm1.is_started())
        self.assertFalse(vm1.is_running())
        self.assertTrue(vm1.terminal())
        self.assertTrue(vm1.kill())
        ret = vm1.start()
        self.assertTrue(ret)

        # sleep 2 seconds in case of name conflicts
        time.sleep(2)

        # vm 2
        vm2 = self.vm_mgr.create_vm()
        vm2 : VMInstance
        self.assertTrue(vm2)
        ret = vm2.init()
        self.assertTrue(ret)
        self.assertTrue(my_utils.fileExists(vm2.vm_config.img_file))
        self.assertTrue(my_utils.fileExists(vm2.vm_config.pm_file))
        self.assertFalse(vm2.is_started())
        self.assertFalse(vm2.is_running())
        self.assertTrue(vm2.terminal())
        self.assertTrue(vm2.kill())
        ret = vm2.start()
        self.assertTrue(ret)

    def test_run_vm_3(self):
        # vm 1
        vm1 = self.vm_mgr.create_vm()
        vm1 : VMInstance
        self.assertTrue(vm1)
        ret = vm1.init()
        self.assertTrue(ret)
        self.assertTrue(my_utils.fileExists(vm1.vm_config.img_file))
        self.assertTrue(my_utils.fileExists(vm1.vm_config.pm_file))
        self.assertFalse(vm1.is_started())
        self.assertFalse(vm1.is_running())
        self.assertTrue(vm1.terminal())
        self.assertTrue(vm1.kill())
        ret = vm1.start()
        self.assertTrue(ret)

        # sleep 2 seconds in case of name conflicts
        time.sleep(2)

        # vm 2
        vm2 = self.vm_mgr.create_vm()
        vm2 : VMInstance
        self.assertTrue(vm2)
        ret = vm2.init()
        self.assertTrue(ret)
        self.assertTrue(my_utils.fileExists(vm2.vm_config.img_file))
        self.assertTrue(my_utils.fileExists(vm2.vm_config.pm_file))
        self.assertFalse(vm2.is_started())
        self.assertFalse(vm2.is_running())
        self.assertTrue(vm2.terminal())
        self.assertTrue(vm2.kill())
        ret = vm2.start()
        self.assertTrue(ret)

        # check if access ok
        max_wait = 120 # seconds
        time.sleep(30)

        # check vm1
        ttw = 120
        while not vm1.access_ok():
            if ttw <= 0:
                break
            ttw -= 5
            time.sleep(5)
        self.assertTrue(vm1.access_ok())

        # check vm2
        ttw = 120
        while not vm2.access_ok():
            if ttw <= 0:
                break
            ttw -= 5
            time.sleep(5)
        self.assertTrue(vm2.access_ok())


if __name__ == "__main__":
    unittest.main()

