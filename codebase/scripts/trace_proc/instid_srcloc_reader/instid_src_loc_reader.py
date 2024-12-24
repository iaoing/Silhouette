import os
import sys

scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(scripts_dir)

from utils.logger import global_logger

class InstIdSrcLocEntry:
    """The instruction id, source location entry"""
    def __init__(self, instid, src, lno):
        self.id = instid
        self.src = src
        self.lno = lno
    
    def __str__(self):
        return self.src + ": " + str(self.lno)

    def __repr__(self) -> str:
        return self.__str__()

    def to_pm_trace_str(self):
        if self.id == -1 or self.lno == -1:
            return "NoSrc:0"
        return self.src + ":" + str(self.lno)
    
class InstIdSrcLocReader:
    """Read instructrion id source location."""
    def __init__(self, fname = None):
        # inst_id : entry
        self.id_loc_map = dict()
        if fname != None:
            self.read_from_file(fname)

    def read_from_file(self, fname):
        cnt = 0
        fd = open(fname, 'r')
        for line in fd:
            line = line.strip()
            if len(line) == 0:
                continue

            cnt += 1
            ll = line.strip().split(":")
            entry = InstIdSrcLocEntry(int(ll[0]), ll[1], int(ll[2]))
            self.id_loc_map[int(ll[0])] = entry
        fd.close()

        global_logger.info("read %d entries from %s" % (cnt, fname))

    def clear(self):
        self.id_loc_map.clear()
