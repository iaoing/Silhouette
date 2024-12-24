import os
import sys
from enum import Enum

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from workload.filesystem_operations.fsop_type import FSOpType
import scripts.utils.logger as log

class FileSystemOp:
    def __init__(self):
        self.type : FSOpType = FSOpType.OP_UNKNOWN

        # for dir-related operations
        self.dir_path = None

        # for file-related operations
        self.file_path = None

        # file size after truncate
        # since fallocate has a 'keep_size' option, we do not check file size of it
        self.file_size = None

        # for write and append op
        self.write_size = None

        # for write op
        self.write_offset = None

        # for rename, link, symlink ops
        self.src_path = None
        self.dst_path = None

    def __str__(self):
        if self.type == FSOpType.OP_CREATE:
            return f"create {self.file_path}"

        elif self.type == FSOpType.OP_UNLINK:
            return f"unlink {self.file_path}"

        elif self.type == FSOpType.OP_MKDIR:
            return f"mkdir {self.dir_path}"

        elif self.type == FSOpType.OP_RMDIR:
            return f"rmdir {self.dir_path}"

        elif self.type == FSOpType.OP_APPEND:
            return f"append {self.file_path} {self.write_size}"

        elif self.type == FSOpType.OP_WRITE:
            return f"write {self.file_path} {self.write_size} {self.write_offset}"

        elif self.type == FSOpType.OP_LINK:
            return f"link {self.src_path} {self.dst_path}"

        elif self.type == FSOpType.OP_SYMLINK:
            return f"symlink {self.src_path} {self.dst_path}"

        elif self.type == FSOpType.OP_SYMLINK:
            return f"rename {self.src_path} {self.dst_path}"

        elif self.type == FSOpType.OP_TRUNCATE:
            return f"truncate {self.file_path} {self.file_size}"

        elif self.type == FSOpType.OP_FALLOCATE:
            return f"fallocate {self.file_path} {self.file_size}"

        else:
            return "unknown"

    def deduce_from_oracle_comment(self, op_str):
        op_attrs = op_str.split(' ')

        if 'open' == op_attrs[0] and 'O_CREAT' in op_attrs[2]:
            self.type = FSOpType.OP_CREATE
            self.file_path = op_attrs[1]

        elif 'create' == op_attrs[0]:
            self.type = FSOpType.OP_CREATE
            self.file_path = op_attrs[1]

        elif 'unlink' == op_attrs[0]:
            self.type = FSOpType.OP_UNLINK
            self.file_path = op_attrs[1]

        if 'mkdir' == op_attrs[0]:
            self.type = FSOpType.OP_MKDIR
            self.dir_path = op_attrs[1]

        if 'rmdir' == op_attrs[0]:
            self.type = FSOpType.OP_RMDIR
            self.dir_path = op_attrs[1]

        if 'append' == op_attrs[0]:
            self.type = FSOpType.OP_APPEND
            self.file_path = op_attrs[1]
            self.write_size = int(op_attrs[2])

        if 'write' == op_attrs[0] or 'dwrite' == op_attrs[0]:
            self.type = FSOpType.OP_WRITE
            self.file_path = op_attrs[1]
            self.write_offset = int(op_attrs[2])
            self.write_size = int(op_attrs[3])

        if 'link' == op_attrs[0]:
            self.type = FSOpType.OP_LINK
            self.src_path = op_attrs[1]
            self.dst_path = op_attrs[2]

        if 'symlink' == op_attrs[0]:
            self.type = FSOpType.OP_SYMLINK
            self.src_path = op_attrs[1]
            self.dst_path = op_attrs[2]

        if 'rename' == op_attrs[0]:
            self.type = FSOpType.OP_RENAME
            self.src_path = op_attrs[1]
            self.dst_path = op_attrs[2]

        if 'truncate' == op_attrs[0]:
            self.type = FSOpType.OP_TRUNCATE
            self.file_path = op_attrs[1]
            self.file_size = int(op_attrs[2])

        if 'falloc' == op_attrs[0]:
            self.type = FSOpType.OP_FALLOCATE
            self.file_path = op_attrs[1]

