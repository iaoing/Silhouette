import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase

class EnvPmfs(EnvBase):
    """docstring for EnvBase."""
    def __init__(self):
        pass

    '''Below methods are regarding parameters of specific file systems'''
    def MODULE_NAME(self) -> str:
        '''the file system name'''
        return 'pmfs'

    def MOD_MNT_TYPE(self) -> str:
        return 'pmfs'

    def FS_MODULE_SRC_DIR(self) -> str:
        # return "%s/thirdPart/pmfs-chipmunk-enable-chipmunk-bugs-except-fatal-ones" % (self.GUEST_REPO_HOME())
        return "%s/thirdPart/pmfs-chipmunk-disable-chipmunk-bugs" % (self.GUEST_REPO_HOME())

    def MOD_INS_PARA(self) -> str:
        return ' '

    def MOD_MNT_PARA(self) -> str:
        return 'init,dbgmask=255'

    def MOD_REMNT_PARA(self) -> str:
        return 'dbgmask=255'

    def RUNTIME_TRACE_SRC(self) -> str:
        return "%s/codebase/trace/runtime/pmfs/KernelTracing.c" % (self.GUEST_REPO_HOME())

    def FS_OP_MAP(self) -> dict:
        return {
            'write' : ['pmfs_xip_file_write'],
            'append' : ['pmfs_xip_file_write'],
            'create' : ['pmfs_create'],
            'umount' : ['pmfs_put_super'],
            'mkdir' : ['pmfs_mkdir'],
            'fallocate' : ['pmfs_fallocate'],
            'link' : ['pmfs_link'],
            'unlink' : ['pmfs_unlink'],
            'rename' : ['pmfs_rename'],
            'truncate' : ['pmfs_notify_change'],
            'symlink' : ['pmfs_symlink'],
            'rmdir' : ['pmfs_rmdir'],
        }

    def IGNORE_STAT_ATTR_SET(self) -> set:
        return None
