import difflib
import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from tools.disk_content.disk_content_wrap import call_get_content
from tools.scripts.disk_content.ctx_file_reader import CtxFileReader
from tools.scripts.disk_content.dentry_attr import DiskEntryAttrs
from tools.scripts.disk_content.disk_content_diff import diff_ctx
from scripts.utils.logger import global_logger


class DiskContent(object):
    def __init__(self):
        self.entries_path_map = dict()
        self.ctx_reader = None
        self.diff_buf = ''
        self.diff_nums = 0

    def read_from_ctx_file(self, fname):
        self.ctx_reader = CtxFileReader(fname = fname)
        self.entries_path_map = self.ctx_reader.entries_path_map

    def read_from_lines(self, lines):
        self.ctx_reader = CtxFileReader(lines=lines)
        self.entries_path_map = self.ctx_reader.entries_path_map

    def get_ctx_from_path(self, path, desc = ''):
        ctx = call_get_content(path, desc)
        lines = ctx.split('\n')
        self.read_from_lines(lines)

    def diff(self, other):
        self.diff_buf, self.diff_nums = diff_ctx(self.entries_path_map, other.entries_path_map)
        return self.diff_buf, self.diff_nums

    def __str__(self):
        if (self.ctx_reader):
            return self.ctx_reader.__str__()
        return ''
