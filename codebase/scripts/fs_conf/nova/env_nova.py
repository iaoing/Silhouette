import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase

class EnvNova(EnvBase):
    """docstring for EnvBase."""
    def __init__(self):
        pass

    '''Below methods are regarding parameters of specific file systems'''
    def MODULE_NAME(self) -> str:
        '''the file system name'''
        return 'nova'

    def MOD_MNT_TYPE(self) -> str:
        return 'NOVA'

    def FS_MODULE_SRC_DIR(self) -> str:
        # return "%s/thirdPart/nova-chipmunk-enable-chipmunk-bugs-except-fatal-ones" % (self.GUEST_REPO_HOME())
        return "%s/thirdPart/nova-chipmunk-disable-chipmunk-bugs" % (self.GUEST_REPO_HOME())

    def MOD_INS_PARA(self) -> str:
        # return 'metadata_csum=0 data_csum=0 data_parity=0 dram_struct_csum=0'  # NOVA
        return 'metadata_csum=1 data_csum=1 data_parity=1 dram_struct_csum=0'   # NOVA_FORTIS, enable dram struct csum will crash for every test.
        # return 'metadata_csum=1 data_csum=1 data_parity=1 dram_struct_csum=1'   # NOVA_FORTIS

    def MOD_MNT_PARA(self) -> str:
        # return 'init,dax,relatime,dbgmask=0'
        return 'init,dax,relatime,dbgmask=0,data_cow'

    def MOD_REMNT_PARA(self) -> str:
        # return 'dax,relatime,dbgmask=0'
        return 'dax,relatime,dbgmask=0,data_cow'

    def RUNTIME_TRACE_SRC(self) -> str:
        return "%s/codebase/trace/runtime/NOVA/KernelTracing.c" % (self.GUEST_REPO_HOME())

    def FS_OP_MAP(self) -> dict:
        return {
            'create' : ['nova_create'],
            'unlink' : ['nova_unlink'],
            'mkdir' : ['nova_mkdir'],
            'rmdir' : ['nova_rmdir'],
            'append' : ['nova_dax_file_write'],
            'write' : ['nova_dax_file_write'],
            'link' : ['nova_link'],
            'symlink' : ['nova_symlink'],
            'rename' : ['nova_rename'],
            'truncate' : ['nova_notify_change'],
            'fallocate' : ['nova_fallocate'],
            'umount' : ['nova_put_super'],
        }

    def IGNORE_STAT_ATTR_SET(self) -> set:
        return {'File_#Blocks'}
