"""
Used to maintain VM configration
"""
import os, sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.vm_mgr.socket_port import find_first_available_port
from scripts.utils.utils import getTimestamp
from scripts.utils.logger import global_logger

class VMConfig:
    def __init__(self, str_id, num_cpu, mem_size_gb, pm_file, pm_size_mb, img_file, vnc_num, comm_port, dram_emulate_pm) -> None:
        self.str_id = str_id
        self.num_cpu = num_cpu
        self.mem_size_gb = mem_size_gb  # in GB
        self.pm_file = pm_file
        self.pm_size_mb = pm_size_mb  # in MB
        self.img_file = img_file
        self.vnc_num = vnc_num
        # comm_port is used to establish the TCP connection between host and guest.
        # this port is the host listening port
        self.comm_port = comm_port
        #
        self.dram_emulate_pm = dram_emulate_pm

    def __str__(self):
        return "str_id: %s, num cpus: %d, mem size: %d, " \
               "pm file: %s, pm size: %d, img file: %s, " \
               "vnc num: %d, comm port: %d, dram emulate pm: %s" % \
                (self.str_id, self.num_cpu, self.mem_size_gb,
                 self.pm_file, self.pm_size_mb, self.img_file,
                 self.vnc_num, self.comm_port, str(self.dram_emulate_pm))

    def __repr__(self) -> str:
        return self.__str__()