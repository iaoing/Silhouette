import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase

class EnvPhoney(EnvBase):
    """docstring for EnvBase."""
    def __init__(self):
        pass

    '''Below methods are regarding parameters of specific file systems'''
    def MODULE_NAME(self) -> str:
        '''the file system name'''
        assert False, "Phoney environment"

    def MOD_MNT_TYPE(self) -> str:
        assert False, "Phoney environment"

    def FS_MODULE_SRC_DIR(self) -> str:
        assert False, "Phoney environment"

    def MOD_INS_PARA(self) -> str:
        assert False, "Phoney environment"

    def MOD_MNT_PARA(self) -> str:
        assert False, "Phoney environment"

    def MOD_REMNT_PARA(self) -> str:
        assert False, "Phoney environment"

    def RUNTIME_TRACE_SRC(self) -> str:
        assert False, "Phoney environment"

    def FS_OP_MAP(self) -> dict:
        assert False, "Phoney environment"

    def IGNORE_STAT_ATTR_SET(self) -> set:
        return None
