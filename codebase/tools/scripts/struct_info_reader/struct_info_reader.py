import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from tools.scripts.struct_info_reader.struct_entry import StructInfo, StructMemberVar
from scripts.utils.logger import global_logger

class StructInfoReader:
    def __init__(self, fname) -> None:
        self.struct_dict = dict()

        self.__init(fname)

        # map a struct name to its father struct name and the offset
        # parent struct name : set of tuple(var's struct (type) name, offset in parent struct)
        self.nested_stname_to_var_stname_dict = dict()
        # map a struct name to a set of its sub struct name
        # var struct (type) name : set of tuple(parent struct name, offset in parent struct)
        self.nested_var_stname_to_parent_stname_dict = dict()
        self.__init_nested()

    def contains_stname(self, stname):
        return stname in self.struct_dict

    def get_parent_info_set(self, name) -> set:
        if name in self.nested_var_stname_to_parent_stname_dict:
            return self.nested_var_stname_to_parent_stname_dict[name]
        return set()

    def __init(self, fname):
        fd = open(fname, 'r')
        lines = fd.readlines()
        fd.close()

        struct_info = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            elif line.startswith("STRUCT RECORD"):
                if struct_info != None:
                    struct_info.finalize()
                    if struct_info.struct_name in self.struct_dict:
                        err_msg = "duplicate struct name, %s" % (str(struct_info))
                        global_logger.error(err_msg)
                        assert False, err_msg
                    self.struct_dict[struct_info.struct_name] = struct_info
                struct_info = StructInfo()
            elif struct_info != None:
                struct_info.add_line(line)
            else:
                err_msg = "invalid record for a struct info, %s" % (line)
                global_logger.error(err_msg)
                assert False, err_msg

    def __init_nested(self):
        for name, stinfo in self.struct_dict.items():
            for var in stinfo.children:
                if var.type_name in self.struct_dict:
                    if name not in self.nested_stname_to_var_stname_dict:
                        self.nested_stname_to_var_stname_dict[name] = set()
                    self.nested_stname_to_var_stname_dict[name].add(tuple([var.type_name, var.offset_bytes]))
                    if var.type_name not in self.nested_var_stname_to_parent_stname_dict:
                        self.nested_var_stname_to_parent_stname_dict[var.type_name] = set()
                    self.nested_var_stname_to_parent_stname_dict[var.type_name].add(tuple([name, var.offset_bytes]))

        log_msg = ""
        for name, ss in self.nested_stname_to_var_stname_dict.items():
            log_msg += "%s's sub-struct: " % (name)
            for pair in ss:
                log_msg += "%s(%d), " % (pair[0], pair[1])
            log_msg += "\n"
        for name, ss in self.nested_var_stname_to_parent_stname_dict.items():
            log_msg += "%s's super-struct: " % (name)
            for pair in ss:
                log_msg += "%s(%d), " % (pair[0], pair[1])
            log_msg += "\n"
        global_logger.debug(log_msg)

    def dbg_detail_info(self) -> str:
        data = ""
        for _, st in self.struct_dict.items():
            data += str(st) + "\n"
        return data
