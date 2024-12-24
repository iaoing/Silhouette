import os
import sys
from intervaltree import Interval, IntervalTree
from copy import deepcopy

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_addr
from tools.scripts.struct_info_reader.struct_entry import StructInfo, StructMemberVar
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason, MechPMStoreEntry
from scripts.mech_reason.mech_link.mech_link_entry import LinkEntryWrapper, MechLinkEntry
from scripts.utils.const_var import POINTER_SIZE
from scripts.utils.logger import global_logger

class MechLinkReason:
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

    def __init__(self, split_entry : OpTraceEntry,
                 pmstore_reason : MechPMStoreReason,
                 st_index : StInfoIndex) -> None:
        self.entry_list = []

        self.__init(split_entry, pmstore_reason, st_index)

        # index from address to the link entry, can be used to check if a address in a link
        self.addr_entry_iv_tree = IntervalTree()
        self.__init_iv_tree()

        self.__init_mech_id()

    def __build_link_from_pmstore(self, link_pmstore_list : list, # a list of pmstores
                                  visited : set, # visited pmstore
                                  pmstore : MechPMStoreEntry,
                                  split_entry : OpTraceEntry,
                                  pmstore_reason : MechPMStoreReason,
                                  st_index : StInfoIndex):
        '''Return none of a new list. This is a DFS'''
        if pmstore in visited:
            return
        visited.add(pmstore)

        # check if a store is a pointer and pm address
        if pmstore.op.size == POINTER_SIZE and \
                is_pm_addr(pmstore.op.addr, split_entry.pm_addr, split_entry.pm_size):
            # check if the stored value inside it is a pm address
            dest_addr = int.from_bytes(pmstore.op.sv_entry.data,
                                        byteorder='little',
                                        signed=False)
            # convert from physical address to virtual address
            dest_addr += split_entry.pm_addr
            # check if this address is a valid pm address.
            if dest_addr == split_entry.pm_addr or \
                    not is_pm_addr(dest_addr, split_entry.pm_addr, split_entry.pm_size):
                return None

            # get the pmstore of this operation
            # this store should be a pointer-sized update
            candidates = pmstore_reason.get_entry_set_by_addr(dest_addr)
            # filter out stores that its address does not match the dest addr,
            # and either not the pointer size or the header of a struct.
            candidates = [x for x in candidates if x.op.addr == dest_addr]
            global_logger.debug(str(candidates))
            candidates = [x for x in candidates if \
                          ((x.op.size == POINTER_SIZE) or \
                           (x.op.stinfo_match and x.op.stinfo_match.addr == dest_addr))]
            if len(candidates) == 0:
                return None
            global_logger.debug(str(candidates))

            # find possible pointers in the struct
            target = []
            struct_list = []
            for store in candidates:
                if store.op.stinfo_match and store.op.stinfo_match.addr == dest_addr:
                    struct_list.append([dest_addr, store.op.stinfo_match.stinfo])
                else:
                    target.append(store)

            # figure out nested struct
            def helper_nested_struct(struct_list, st_index : StInfoIndex, st_name_visited : set):
                # return true if has progress
                has_progress = False
                for pair in struct_list:
                    stinfo : StructInfo = pair[1]
                    if stinfo.struct_name in st_name_visited:
                        continue
                    else:
                        st_name_visited.add(stinfo.struct_name)
                    # handle the nested struct
                    if stinfo.struct_name in st_index.stinfo_reader.nested_var_stname_to_parent_stname_dict:
                        for parent in st_index.stinfo_reader.nested_var_stname_to_parent_stname_dict[stinfo.struct_name]:
                            parent_name = parent[0]
                            offset = parent[1]
                            struct_list.append([pair[0] - offset, st_index.stinfo_reader.struct_dict[parent_name]])
                            has_progress = True
                    if stinfo.struct_name in st_index.stinfo_reader.nested_stname_to_var_stname_dict:
                        for child in st_index.stinfo_reader.nested_stname_to_var_stname_dict[stinfo.struct_name]:
                            child_name = child[0]
                            offset = child[1]
                            struct_list.append([pair[0] + offset, st_index.stinfo_reader.struct_dict[child_name]])
                            has_progress = True
                return has_progress

            # find all nested structure
            global_logger.debug(str(struct_list))
            st_name_visited = set()
            while helper_nested_struct(struct_list, st_index, st_name_visited):
                pass
            global_logger.debug(str(struct_list))

            # find all pointer pmstore within the struct
            global_logger.debug(str(target))
            for pair in struct_list:
                st_addr = pair[0]
                stinfo : StructInfo = pair[1]
                for var in stinfo.children:
                    if var.size_bytes == POINTER_SIZE:
                        # find the corresponding pm stores
                        co_stores = pmstore_reason.get_entry_set_by_addr(st_addr + var.offset_bytes)
                        co_stores = [x for x in co_stores if x.op.addr == st_addr + var.offset_bytes]
                        target += co_stores

            if len(target) == 0:
                return None
            global_logger.debug(str(target))

            if len(link_pmstore_list) == 0:
                link_pmstore_list = [pmstore]

            new_link_pmstore_list = []

            # premute all possible links
            # list: [[1,2], [1,3]]
            # target: [4,5]
            # -> [[1,2,4], [1,2,5], [1,3,4], [1,3,5]]
            for store in target:
                new_list = deepcopy(link_pmstore_list)
                new_list.append(store)
                tmp = self.__build_link_from_pmstore(new_list, visited, store,
                                                split_entry, pmstore_reason, st_index)

                if not tmp:
                    new_link_pmstore_list.append(new_list)
                else:
                    # due to the recursion, tmp could contain lists
                    def get_all_inner_lists(lst):
                        result = []
                        for item in lst:
                            if isinstance(item, list):
                                result.append(item)
                                result.extend(get_all_inner_lists(item))
                        return result
                    inner_list = get_all_inner_lists(tmp)
                    if not inner_list:
                        new_link_pmstore_list.append(tmp)
                    else:
                        new_link_pmstore_list += inner_list
                return new_link_pmstore_list

    def __init(self, split_entry : OpTraceEntry,
               pmstore_reason : MechPMStoreReason,
               st_index : StInfoIndex):
        unique_entry_key_set = set()
        visited = set()
        for entry in pmstore_reason.entry_list:
            entry : MechPMStoreEntry

            link_pmstore_list = []
            link_pmstore_list = self.__build_link_from_pmstore(link_pmstore_list,
                                                          visited, entry,
                                      split_entry, pmstore_reason, st_index)

            global_logger.debug(str(link_pmstore_list))
            if not link_pmstore_list:
                continue

            for lst in link_pmstore_list:
                if not isinstance(lst, list) or len(lst) <= 1:
                    continue
                link_entry = MechLinkEntry(split_entry.pid, lst, st_index, split_entry.pm_addr, split_entry.pm_size)
                key = link_entry.get_id_str()
                if key not in unique_entry_key_set:
                    log_msg = "add a new link entry, %s" % (str(key))
                    global_logger.debug(log_msg)
                    unique_entry_key_set.add(key)
                    self.entry_list.append(link_entry)
                else:
                    log_msg = "found a duplicated entry, %s" % (str(key))
                    global_logger.debug(log_msg)

    def __init_iv_tree(self):
        for entry in self.entry_list:
            entry : MechLinkEntry
            self.addr_entry_iv_tree |= entry.addr_iv_tree

    def __init_mech_id(self):
        num = 0
        for entry in self.entry_list:
            num += 1
            entry.mech_id = num

    def get_link_header_list_by_addr(self, addr) -> list:
        rst = []
        ivs = self.addr_entry_iv_tree[addr]
        for iv in ivs:
            node : LinkEntryWrapper = iv.data
            if node.header not in rst:
                rst.append(node.header)
        return rst

    def dbg_get_detail(self):
        data = ""
        for entry in self.entry_list:
            entry : MechLinkEntry
            data += "Link %d\n" % (entry.mech_id)
            data += entry.dbg_get_detail() + "\n" + "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
