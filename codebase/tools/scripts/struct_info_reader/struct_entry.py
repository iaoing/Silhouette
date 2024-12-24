import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger

class StructMemberVar:
    """docstring for StructMemberVar."""
    def __init__(self, father_name, line):
        self.father_name   = father_name
        self.type_name     = None  # only the type/struct name
        self.raw_type_name = None  # includes *, [], etc.
        self.var_name      = None
        self.size_bits     = None
        self.size_bytes    = None
        self.offset_bits   = None
        self.offset_bytes  = None
        self.is_ptr        = False
        self.is_ary        = False

        self.__init(line)

    def __init(self, line):
        lst = line.strip().split(",")

        self.type_name     = lst[0]
        self.raw_type_name = lst[0]
        self.var_name      = lst[1]
        self.size_bits     = int(lst[2])
        self.size_bytes    = int(lst[3])
        self.offset_bits   = int(lst[4])
        self.offset_bytes  = int(lst[5])
        self.is_ptr        = bool(int(lst[6]))
        self.is_ary        = bool(int(lst[7]))

        if self.var_name == '' or not self.var_name or self.var_name == None:
            self.var_name = 'anonymous'

        if self.type_name.startswith("struct "):
            self.type_name = self.type_name[len("struct "):]
        while self.type_name.endswith("*"):
            self.type_name = self.type_name[:-1]
        if "[" in self.type_name and "]" in self.type_name:
            p1 = self.type_name.find('[')
            p2 = self.type_name.find(']')
            self.type_name = self.type_name[:p1] + self.type_name[p2+1:]
        self.type_name = self.type_name.strip()

    def __str__(self) -> str:
        return "%s %s" % (self.raw_type_name, self.var_name)

    def __repr__(self) -> str:
        return self.__str__()

    def __member(self) -> tuple:
        return (self.father_name, self.type_name, self.var_name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, StructMemberVar):
            return False
        return self.__member() == other.__member()

    def __hash__(self) -> int:
        return hash(self.__member())

class StructInfo:
    def __init__(self) -> None:
        self.struct_name = None
        self.size_bits   = None
        self.size_bytes  = None

        self.children = []

    def __str__(self) -> str:
        data = "struct %s, %d, %d\n" % (self.struct_name, self.size_bits, self.size_bytes)
        for child in self.children:
            data += str(child).strip() + "\n"
        return data

    def __repr__(self) -> str:
        return self.__str__()

    def __member(self) -> tuple:
        return (self.struct_name, self.size_bits, self.size_bytes, len(self.children))

    def __eq__(self, other) -> bool:
        if not isinstance(other, StructInfo):
            return False
        return self.__member() == other.__member()

    def __hash__(self) -> bool:
        return hash(self.__member())

    def add_line(self, line : str):
        if line.count(',') == 2:
            self.add_struct_header(line)
        elif line.count(',') == 7:
            self.add_member_var(line)
        else:
            err_msg = "invalid record for a struct info, %s" % (line)
            global_logger.error(err_msg)
            assert False, err_msg

    def add_struct_header(self, line):
        if self.struct_name != None:
            err_msg = "duplicate struct header, %s, %s" % (line, self.__str__())
            global_logger.error(err_msg)
            assert False, err_msg

        self._raw_line = line

        lst = line.strip().split(',')

        self.struct_name = lst[0]
        self.size_bits   = int(lst[1])
        self.size_bytes  = int(lst[2])

    def add_member_var(self, line):
        if self.struct_name == None:
            err_msg = "no struct header, %s, %s" % (line, self.__str__())
            global_logger.error(err_msg)
            assert False, err_msg

        child = StructMemberVar(self.struct_name, line)
        self.children.append(child)

    def finalize(self):
        assert self.struct_name != None, "invalid struct info, %s" % (self.__str__())
        self.children.sort(key = lambda x : x.offset_bits)