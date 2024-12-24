import os
import sys
from intervaltree import Interval, IntervalTree

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_entry, is_pm_addr
from tools.scripts.struct_info_reader.struct_entry import StructInfo, StructMemberVar
from scripts.trace_proc.trace_stinfo.addr_to_stinfo_entry import AddrToStInfoEntry
from scripts.utils.utils import isUserSpaceAddr, isKernelSpaceAddr
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason, MechPMStoreEntry
from scripts.utils.logger import global_logger

class LinkEntryWrapper:
    def __init__(self, pid, header, store, prev, next, st_index : StInfoIndex) -> None:
        self.pid = pid
        self.pm_store : MechPMStoreEntry = store

        # the header of this link
        self.header = header
        # the next link entry
        # it could be None if it is the last entry in the link
        self.prev = prev
        self.next = next

        # a list of [StructInfo, addr]
        self.var : StructMemberVar = None
        # the most outter (biggest) struct in the first
        self.struct_info = []
        self.__init_struct_info(st_index)

    def get_opid_seq_list(self) -> list:
        return []

    def get_safe_data_seq_list(self) -> list:
        return []

    def get_unsafe_data_seq_list(self) -> list:
        return []

    def __str__(self) -> str:
        data = ""
        for pair in self.struct_info:
            data += "%s(%s)." % (pair[0].struct_name, hex(pair[1]))
        if self.next:
            data += "%s(%s)" % (str(self.var), hex(self.pm_store.op.addr))
            # TODO: do not know why self.var could be a none type.
            # data += "%s(%s)" % (self.var.var_name, hex(self.pm_store.op.addr))
        return data

    def __repr__(self) -> str:
        return self.__str__()

    def __init_struct_info(self, st_index : StInfoIndex):
        if not self.pm_store.op.stinfo_match:
            return

        # get the start address of the struct the store belonged to.
        self.var = self.pm_store.op.stinfo_match.get_var_by_addr(self.pm_store.op.addr)
        if isinstance(self.var, list):
            self.var = self.var[0]
        if self.var == None or not self.var:
            err_msg = "cannot find the variable for a link pointer, [%s], [%s], [%s], [%s], [%s], [%s], [%s]" % \
                    (self.var == None, not self.var, not isinstance(self.var,StructMemberVar), \
                     type(self.var), str(self.var), str(self.pm_store), str(self.pm_store.op.stinfo_match))
            global_logger.error(err_msg)
            assert False, err_msg

        dbg_msg = "found the variable of the link pointer: %s" % (str(self.var))
        global_logger.debug(dbg_msg)

        st_addr = self.pm_store.op.addr - self.var.offset_bytes
        self.struct_info.append([self.pm_store.op.stinfo_match.stinfo, st_addr])

        # TODO: handle multiple nested structure (recursively find parents).
        parent_info_set = st_index.stinfo_reader.get_parent_info_set(self.pm_store.op.stinfo_match.stinfo.struct_name)
        if not parent_info_set:
            log_msg = "no parent info for struct, %s" % (self.pm_store.op.stinfo_match.stinfo.struct_name)
            global_logger.debug(log_msg)
            return
        global_logger.debug(str(parent_info_set))

        iv = st_index.point_query_iv(self.pid, self.pm_store.op.addr)
        global_logger.debug(iv)
        if not iv:
            return

        for en in iv.data:
            en : AddrToStInfoEntry
            flag = False
            for parent_info in parent_info_set:
                if en.stinfo.struct_name == parent_info[0]:
                    self.struct_info.append([en.stinfo, st_addr - parent_info[1]])
                    flag = True
                    break
            if flag:
                break

        # reverse the list that the most outter structure in the first
        self.struct_info.reverse()

    def get_link_node_addr_range(self) -> list:
        '''returns the address range of the link pointer node (not the link entry)'''
        if not self.next:
            # if does not have next node, we think this entry does not contain a link pointer node
            return []
        addr1 = self.struct_info[-1][1]
        addr2 = addr1 + self.struct_info[-1][0].size_bytes
        return [addr1, addr2]

    def get_addr_range(self, ignore_link_node_addr) -> list:
        '''returns the address range of the node'''
        addr1 = self.struct_info[0][1]
        addr2 = addr1 + self.struct_info[0][0].size_bytes
        if not ignore_link_node_addr or not self.next:
            return [[addr1, addr2]]

        # use interval tree to handle the case: [0, 100] where the link pointer
        # node in the middle [50, 60]
        iv_tree = IntervalTree()
        iv_tree[addr1 : addr2] = ''

        addr1 = self.struct_info[-1][1]
        addr2 = addr1 + self.struct_info[-1][0].size_bytes
        iv_tree.chop(addr1, addr2)

        rst = [[x.begin, x.end] for x in iv_tree.items()]

        return rst

    def get_id_key(self):
        key = ""
        for pair in self.struct_info:
            key += "%s(%s)." % (pair[0].struct_name, hex(pair[1]))
        if self.next:
            key += "%s(%s)" % (str(self.var.var_name), hex(self.pm_store.op.addr))
        return key

class MechLinkEntry:
    '''
    The link entry is represented by one variable, a.k.a., the pointer to another entry.
    Since the entry in single linked-list could be various struct types, we cannot
    identify them by the struct info. We can only identify the pointer first,
    then obtain the struct from the address of the pointer.
    Besides, the pointer could point to the pointer of the next node, or point
    to the head of the next node.
    Therefore, to identify a linked list, processes:
    1. store all pointer (8 bytes) that points to a PM address to a map
       (each PM pointer and the destination can form a link that contain
        to items, the pointer and the destination address. It may be not a
        valid linked-list, but they are a link. E.g., the journal pointer
        that pointers to the journal tail.)
    2. iterate pointer one by one and get the destination PM address
    3. if the destination address is a PM pointer in the dict, we keep going to
       track the next destination, until we reach the end.
    4. if the destination address is the head of a struct, search variables inside
       the struct to find a pointer that in the dict. Then keep tracking the next
       destination (the next struct head) until we reach the end.
    5. if the destination is neither a pointer nor a struct head, we do not think
       it could be a link.
    '''


    def __init__(self, pid : int, pmstore_list : list, st_index : StInfoIndex, pm_addr, pm_size) -> None:
        self.pid = pid
        self.pm_addr = pm_addr
        self.pm_size = pm_size

        # the start of the link
        self.header : LinkEntryWrapper = None
        self.__build_link(pmstore_list, st_index)

        # index from address to the link entry
        self.addr_iv_tree = IntervalTree()
        self.__build_iv_tree()

    def __build_link(self, pmstore_list : list, st_index : StInfoIndex):
        prev = None
        for pmstore in pmstore_list:
            pmstore : MechPMStoreEntry
            if prev == None:
                prev = LinkEntryWrapper(self, self.pid, pmstore, None, None, st_index)
                self.header = prev
            else:
                curr = LinkEntryWrapper(self, self.pid, pmstore, prev, None, st_index)
                prev.next = curr

    def __build_iv_tree(self):
        curr = self.header
        while curr:
            curr : LinkEntryWrapper
            if len(curr.struct_info) > 0:
                start_addr = curr.struct_info[0][1]
                end_addr = curr.struct_info[0][1] + curr.struct_info[0][0].size_bytes
                self.addr_iv_tree[start_addr:end_addr] = curr
            curr = curr.next

    def __str__(self) -> str:
        return str(self.addr_iv_tree)

    def __repr__(self) -> str:
        return self.__str__()

    def addr_in_link(self, addr):
        return len(self.addr_iv_tree[addr]) > 0

    def get_available_addr_range(self, start_addr, end_addr, ignore_link_struct) -> list:
        '''
        Returns a list of address range in the linked list.
        Can select to contain the struct itself or not. For example,
        page[0, 1024) -> link_node [1000, 1024) -> next [1016, 1024) = page [10240, 11264)
        If ignore_link_struct, it returns the address [[0, 1000), [10240, 11264)]
        Since we do not if the next page has a link node (may have different struct type or link node),
        the whole range of the next page is returned.
        If not ignore_link_struct, it returns [[0, 1024), [10240, 11264)]
        '''
        writeable_range = []
        node = self.header
        while node:
            addr_range = node.get_addr_range(ignore_link_node_addr=True)
            if addr_range:
                writeable_range += addr_range
            node = node.next
        # does not need to sort them, since the next node could have a lower address range
        global_logger.debug(str([[hex(x[0]), hex(x[1])] for x in writeable_range]))

        rst = []
        for wr in writeable_range:
            addr1 = wr[0]
            addr2 = wr[1]
            if addr1 <= start_addr <= addr2:
                # when start addr == addr2 which means we reach the beginning,
                # however, it is not a valid range, we need to remove the 0 range later.
                addr1 = start_addr
            elif len(rst) == 0:
                # the start address have not reach the beginning. E.g.,
                # [0, 10), [20, 30) while the start address is 25
                continue

            if addr1 <= end_addr <= addr2:
                # reach the end of the end address
                addr2 = end_addr
                rst.append([addr1, addr2])
                break
            rst.append([addr1, addr2])

        rst = [x for x in rst if x[0] != x[1]]

        return rst

    def get_id_str(self):
        '''return the id in string, used to identify duplicates'''
        key = ""
        curr : LinkEntryWrapper = self.header
        while curr:
            key += str(curr) + " -> "
            curr = curr.next
        return key

    def dbg_get_detail(self):
        data = ""
        curr : LinkEntryWrapper = self.header
        while curr:
            # data += "%s.%s -> " % (curr.pm_store.op.stinfo_match.stinfo.struct_name,
            #                        str(curr.pm_store.op.var_list))
            data += str(curr) + " -> "
            curr = curr.next
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
