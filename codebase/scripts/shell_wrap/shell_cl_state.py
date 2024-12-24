"""Represent the return values from a shell running"""
import os
import sys

database_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(database_dir)

from scripts.utils.resource_record import ResourceRecord
from scripts.utils.proc_state import is_process_running, kill_process
from scripts.utils.logger import global_logger

class ShellCLState:
    """docstring for ShellCLState."""
    def __init__(self, cmd):
        self.cmd = cmd

        self.code = None
        self.stdout = b''
        self.stderr = b''

        self.proc = None

    def msg(self, prefix=""):
        return prefix + self.cmd + ", " + str(self.code) \
                      + ", " + str(self.stdout) \
                      + ", " + str(self.stderr)

    def is_vm_running(self, key) -> bool:
        if key == None:
            key = self.cmd
        ret = is_process_running(key_word=key)
        if ret:
            global_logger.debug("vm %s is running" % (key))
        else:
            global_logger.debug("vm %s is not running" % (key))
        return ret

    def is_running(self, vm, vm_key=None) -> bool:
        # if this is a vm start function, we cannot use poll to determine if
        # it is finished.
        if not vm:
            return self.proc.poll() == None
        else:
            return self.is_vm_running(vm_key)

    def terminal_vm(self, key, host_name, ttw) -> bool:
        assert False, "please terminate the VM via vm instance"

    def terminal(self, vm, vm_key=None, host_name=None, ttw=30) -> bool:
        # return False if not terminated.
        if not vm:
            self.proc.stderr.close()
            self.proc.stdout.close()
            self.proc.terminate()
            self.proc.wait()
            return not self.is_running(vm=False)
        else:
            if not self.terminal_vm(vm_key, host_name, ttw):
                return False
            return self.is_vm_running(host_name)

    def kill_vm(self, key) -> bool:
        if key == None:
            key = self.cmd
        return kill_process(key_word=key, match_all_pattern=False)

    def kill(self, vm, vm_key=None) -> bool:
        # return False if not killed.
        if not vm:
            self.proc.stderr.close()
            self.proc.stdout.close()
            self.proc.kill()
            self.proc.wait()
            return not self.is_running(vm=False)
        else:
            if not self.kill_vm(vm_key):
                return False
            return self.is_vm_running(vm_key)
