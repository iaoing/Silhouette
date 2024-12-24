import os, sys
import shutil
import unittest
from unittest.mock import patch, mock_open

scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(scripts_dir)

from utils.ssh_config import SSHConfig, SSHConfigPool

class TestSSHConfigPool(unittest.TestCase):
    def __remove_tmp_files(self, prefix):
        for file_name in os.listdir():
            if file_name.startswith(prefix):
                os.remove(file_name)

    def test_alloc_ssh_config(self):
        shutil.copy(os.path.expanduser("~/.ssh/config"), "test_ssh_config_file_1")

        # Create an instance of SSHConfigPool
        pool = SSHConfigPool("testuser", pool_size=1, ssh_config_file="test_ssh_config_file_1")

        # Allocate an SSHConfig
        ssh = pool.alloc_ssh_config()
        self.assertIsNotNone(ssh)

        # Try to allocate another SSHConfig, but it should be None
        ssh2 = pool.alloc_ssh_config()
        self.assertIsNone(ssh2)

        self.__remove_tmp_files("test_ssh_config_file_1")

    def test_dealloc_ssh_config(self):
        shutil.copy(os.path.expanduser("~/.ssh/config"), "test_ssh_config_file_2")

        # Create an instance of SSHConfigPool
        pool = SSHConfigPool("testuser", pool_size=1, ssh_config_file="test_ssh_config_file_2")

        # Allocate an SSHConfig
        ssh = pool.alloc_ssh_config()
        self.assertIsNotNone(ssh)

        # Deallocate the SSHConfig
        pool.dealloc_ssh_config(ssh)

        # Allocate another SSHConfig, it should not be None
        ssh2 = pool.alloc_ssh_config()
        self.assertIsNotNone(ssh2)

        self.__remove_tmp_files("test_ssh_config_file_2")
    
    def test_destory_ssh_config_1(self):
        shutil.copy(os.path.expanduser("~/.ssh/config"), "test_ssh_config_file_3")

        # Create an instance of SSHConfigPool
        pool = SSHConfigPool("testuser", pool_size=1, ssh_config_file="test_ssh_config_file_3")

        # Allocate an SSHConfig
        ssh = pool.alloc_ssh_config()
        self.assertIsNotNone(ssh)

        # Deallocate the SSHConfig
        pool.dealloc_ssh_config(ssh)

        ret = pool.destory_pool()
        self.assertTrue(ret)

        self.__remove_tmp_files("test_ssh_config_file_3")
    
    def test_destory_ssh_config_2(self):
        shutil.copy(os.path.expanduser("~/.ssh/config"), "test_ssh_config_file_4")

        # Create an instance of SSHConfigPool
        pool = SSHConfigPool("testuser", pool_size=1, ssh_config_file="test_ssh_config_file_4")

        # Allocate an SSHConfig
        ssh = pool.alloc_ssh_config()
        self.assertIsNotNone(ssh)

        ret = pool.destory_pool()
        self.assertFalse(ret)

        self.__remove_tmp_files("test_ssh_config_file_4")

if __name__ == '__main__':
    unittest.main()