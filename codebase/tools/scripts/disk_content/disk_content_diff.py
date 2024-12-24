import difflib
import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from tools.scripts.disk_content.dentry_attr import DiskEntryAttrs
from scripts.utils.logger import global_logger

def diff_ctx(a_entry_path_map, b_entry_path_map, attr_ignore_set : set = None):
    '''return the difference string, and the number of difference entries'''
    diff_buf = ""
    diff_nums = 0

    # different them by the path of entry
    processed_path = set()
    # process all entries in self
    for path, entry in a_entry_path_map.items():
        processed_path.add(path)
        if path in b_entry_path_map:
            buf, nums = entry.diffAttrs(b_entry_path_map[path], attr_ignore_set)
            if nums > 0:
                diff_buf += buf + "\n"
                diff_nums += 1
        else:
            buf, nums = entry.diffAttrsDxStr()
            if nums > 0:
                diff_buf += buf + "\n"
                diff_nums += 1

    # process not processed entries in other
    for path, entry in b_entry_path_map.items():
        if path not in processed_path:
            buf, nums = entry.diffAttrsDxRevsStr()
            if nums > 0:
                diff_buf += buf + "\n"
                diff_nums += 1

    return diff_buf, diff_nums
