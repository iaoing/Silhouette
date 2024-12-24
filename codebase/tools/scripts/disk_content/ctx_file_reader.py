import difflib
import os
from enum import Enum
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from workload.filesystem_operations.fs_operations import FileSystemOp
from tools.scripts.disk_content.dentry_attr import DiskEntryAttrs
from scripts.utils.logger import global_logger

class CtxFileReader:
    """Read the dumped disk content file."""
    def __init__(self, lines : list = None, fname = None):
        self.lines = lines
        if isinstance(self.lines, str):
            self.lines = [x + '\n' for x in self.lines.split("\n")]

        self.has_err_msg = False
        # parse content in file if fname is provided
        self.fname = fname
        self.op_comment = None
        self.fs_op : FileSystemOp = FileSystemOp()
        self.__parseFile()
        # entries may have the same hash value, so, just use list to store them.
        self.entries = []
        self.__initEntries()

        # dict(id, entry)
        self.entries_id_map = dict()
        # dict(path, entry)
        self.entries_path_map = dict()
        self.__initMaps()

    def get_entry_path_map(self):
        return self.entries_path_map

    def deduce_op_type(self):
        if not self.op_comment:
            return None
        if 'open' in self.op_comment and 'O_CREAT' in self.op_comment:
            return

    def __parseFile(self):
        if self.fname:
            fd = open(self.fname, "r", errors="ignore")
            self.lines = fd.readlines()
            fd.close()

        # log_msg = 'read lines from file: %s, %s' % (self.fname, self.lines)
        # global_logger.debug(log_msg)

    def __initEntries(self):
        entry = None
        for line in self.lines:
            if line.startswith('#### '):
                self.op_comment = line.strip()[5:]
                self.fs_op.deduce_from_oracle_comment(self.op_comment)
                continue
            # print(line)
            if not line or line.count(":") == 0 or line.startswith("#"):
                continue
            if 'error' in line:
                self.has_err_msg = True
                continue
            # if line.startswith("Content_ID"):
            if entry == None:
                assert entry == None, "duplicate entry: %s" % (line)
                entry = DiskEntryAttrs()

            entry.addAttr(line)

            # after adding the md5, finalize it.
            if line.startswith("File_MD5"):
                entry.finalize()
                self.entries.append(entry)
                entry = None

    def __initMaps(self):
        for entry in self.entries:
            self.entries_id_map[entry.id] = entry
            self.entries_path_map[entry.path] = entry

    def __str__(self) -> str:
        buf = ""
        if self.op_comment:
            buf += self.op_comment + "\n"
        for entry in self.entries:
            buf += entry.__str__() + "\n"
        return buf
