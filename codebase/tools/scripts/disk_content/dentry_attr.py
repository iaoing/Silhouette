import difflib
import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger
import scripts.utils.logger as log

class DiskEntryAttrs:
    """
    File/Dir attributes for each disk content item.
    The keys of attributes are defined in 'DiskContent.cpp'
    """
    def __init__(self):
        # dict(key -> value) where key is the attribute.
        self.vars = dict()
        # used to store immutable set (frozen set) and used to hash and compare
        self.fzset = set()
        # unique identify
        self.id = -1
        self.path = ""

    def __eq__(self, other) -> bool:
        if not isinstance(other, DiskEntryAttrs):
            return False
        return self.fzset == other.fzset

    def __ne__(self, other) -> bool:
        if isinstance(other, DiskEntryAttrs):
            return self.fzset != other.fzset
        return False

    def __hash__(self) -> int:
        return hash(self.fzset)

    def __str__(self) -> str:
        buf = "ID: %d\nPath: %s\n" % (self.id, self.path)
        for key, val in self.vars.items():
            buf += "%s : %s\n" % (key, val)
        return buf

    def __repr__(self) -> str:
        return self.fzset.__repr__()

    def getVarStr(self, key):
        rst = ""
        if key in self.vars:
            rst = "%s : %s" % (key, self.vars[key])
        return rst

    def diffAttrsDxRevsStr(self):
        return "diff: ???? <-> %s\n" % (self.path), len(self.vars)

    def diffAttrsDxStr(self):
        return "diff: %s <-> ????\n" % (self.path), len(self.vars)

    def diffAttrs(self, other, attr_ignore_set : set = None, attr_check_set : set = None):
        # return the different or none, and the number of diff keys
        if self == other:
            return "", 0

        diff_buf = "diff: %s <-> %s\n" % (self.path, other.path)
        # exclusive or them
        diff_set = self.fzset ^ other.fzset
        diff_keys = set([x[0] for x in diff_set])

        # iterator each diff key
        if isinstance(attr_check_set, set):
            diff_keys = diff_keys & attr_check_set
        if isinstance(attr_ignore_set, set):
            diff_keys = diff_keys - attr_ignore_set

        for key in diff_keys:
            s1 = self.getVarStr(key)
            s2 = other.getVarStr(key)
            assert s1 != s2, "invalid: %s %s" % (s1, s2)
            diff_buf += "- %s\n" % (s1)
            diff_buf += "+ %s\n" % (s2)

        return diff_buf, len(diff_keys)

    def sameAttrValue(self, other, attr_key : str):
        '''Return (bool, diff msg)'''
        if attr_key not in self.vars or attr_key not in other.vars:
            msg = f"No such attribute {attr_key} in {self.vars} or {other.vars}"
            log.global_logger.error(msg)
            return False, msg

        if self.vars[attr_key] != other.vars[attr_key]:
            msg = f"- {self.getVarStr(attr_key)}\n+ {other.getVarStr(attr_key)}"
            return False, msg
        else:
            return True, None

    def finalize(self):
        # check id first
        if self.id < 0 or self.path == "":
            print(self)
            assert False, "invalid attributes"
        # does not need to sort items since we trust it based on the dump order.
        self.fzset = frozenset(self.vars.items())

    def addAttr(self, line : str):
        if self.fzset:
            print(self)
            print(line)
            assert False, "add attribute after finalization"

        if line.count(":") == 0:
            return
        elif line.startswith("Content_ID"):
            self.id = int(line.split(":")[1])
        elif line.startswith("Path"):
            self.path = line.split(":")[1].strip()
        else:
            line = " ".join(line.split())
            key = line.split(":")[0].strip()
            val = line.split(":")[1].strip()
            if key in self.vars:
                print(self)
                print(line)
                assert False, f"duplicate attributes {key} in {self.path}"
            self.vars[key] = val
