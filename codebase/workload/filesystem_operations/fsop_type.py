import os
import sys
from aenum import Enum

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

import scripts.utils.logger as log

class FSOpType(Enum):
    _init_ = 'value string'

    OP_CREATE    = 1, 'create'
    OP_UNLINK    = 2, 'unlink'
    OP_MKDIR     = 3, 'mkdir'
    OP_RMDIR     = 4, 'rmdir'
    OP_APPEND    = 5, 'append'
    OP_WRITE     = 6, 'write'
    OP_LINK      = 7, 'link'
    OP_SYMLINK   = 8, 'symlink'
    OP_RENAME    = 9, 'rename'
    OP_TRUNCATE  = 10, 'truncate'
    OP_FALLOCATE = 11, 'fallocate'
    OP_UMOUNT    = 12, 'umount'
    OP_UNKNOWN   = 255, 'unknown'

    def __str__(self):
        return self.string

    def name(self):
        return self.string

    @classmethod
    def _missing_value_(cls, name):
        for member in cls:
            if member.string == name:
                return member
        print("no ", name, " in Enum")
        exit(1)
