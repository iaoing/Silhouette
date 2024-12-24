import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger

class SrcInfoReader:
    """Read content from src_info dumped file."""
    def __init__(self, fname=None):
        self.src_info_ = set()

        if fname:
            self.add_info_from_file(fname)

    def __contains__(self, e) -> bool:
        return e in self.src_info_

    def add_info_from_file(self, fname):
        cnt = 0
        with open(fname, 'r') as fd:
            for line in fd:
                cnt += 1
                self.src_info_.add(line.strip())
            global_logger.debug("add %d src info from %s, %s" % (cnt, fname, str(self.src_info_)))

    def clear(self):
        self.src_info_.clear()

