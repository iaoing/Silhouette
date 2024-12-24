import os
import sys
from enum import Enum

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from scripts.trace_proc.trace_reader.trace_type import TraceType
from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueEntry
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_entry, is_pm_addr
from scripts.utils.utils import isUserSpaceAddr, isKernelSpaceAddr
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex, StructInfo, AddrToStInfoEntry, StructMemberVar
from scripts.mech_reason.mech_memcpy.mech_memcpy_entry import MechMemcpyEntry
from scripts.mech_reason.mech_memcpy.mech_memcpy_reason import MechMemcpyReason
from scripts.mech_reason.mech_store.mech_pmstore_entry import MechPMStoreEntry
from scripts.mech_reason.mech_store.mech_pmstore_reason import MechPMStoreReason
import scripts.utils.logger as log

class ReplInvariantErrorType(Enum):
    """The error types of replications invariants."""
    NO_STORE_TO_PRIMARY                   = 'no_store_to_primary'
    STORE_TO_PRIMARY_FENCED_AFTER_MEMCPY = 'store_to_primary_fenced_AFTER_memcpy'
    STORE_TO_PRIMARY_NOT_IN_SAME_STRUCT   = 'store_to_primary_not_in_same_struct'
    PRIMARY_AND_REPLICA_DATA_NOT_MATCH    = 'primary_and_replica_data_not_match'

class MechReplEntry:
    def __init__(self):
        self.mech_id = -1
        # When coping from a replica to another one, multiple memcpy and the DRAM copy may involved.
        # For example, in NOVA, it copies data from a PM replica to DRAM first multiple times, then copy the DRAM copy to another PM replica. Another example is copying `dentry`. NOVA copies metadata from one PM replica to another PM replica, and then copies the name of the `dentry`.
        # Thus, the load operations/traces are stored in a list
        # a list of MechMemcpyEntry
        self.load_op_list : list = []
        # TODO: Similarly, the store may involved multiple copies.
        # Only support one copy
        # store op could be the one in the load op list if this is a PM-to-PM replication copy.
        self.store_op : MechMemcpyEntry = None
        # used to get the fence seq
        self.store_pmstore : MechPMStoreEntry = None

        # a list of MechPMStoreEntry
        # the writes to the primary replica
        self.stores_to_primary_replica = []

        # a list of seq that need to be persisted it only (2CP) to test
        self.unsafe_pself_set : set = set()
        # a list of seq that need to be persisted other only (2CP) to test
        self.unsafe_pother_set : set = set()

        self.err_dict : dict = dict()

    def get_all_seq(self) -> set:
        seqs : set = set()
        if self.store_op:
            seqs.add(self.store_op.op_st.seq)
        seqs |= set([x.op.seq for x in self.stores_to_primary_replica])
        return seqs

    def invariant_check(self):
        ''' Returns a list of invariant checking errors. '''
        self.err_dict.clear()
        err_list = []
        # 1. check have stores to the primary
        if len(self.stores_to_primary_replica) == 0:
            err_list.append(ReplInvariantErrorType.NO_STORE_TO_PRIMARY)
            self.err_dict[0] = ReplInvariantErrorType.NO_STORE_TO_PRIMARY
            return err_list

        # 2. check all stores to the primary replica are fenced before the update time of the memcpy and are in the same data structure
        mcp_seq = self.store_op.op_st.seq
        src_struct_addr = None
        dst_addr_range = [self.store_op.op_st.addr, self.store_op.op_st.addr + mcp_seq]
        for pm_store in self.stores_to_primary_replica:
            pm_store : MechPMStoreEntry
            # check fence time
            if pm_store.fence_op.seq >= mcp_seq:
                self.err_dict[pm_store.op.seq] = ReplInvariantErrorType.STORE_TO_PRIMARY_FENCED_AFTER_MEMCPY
                err_list.append(ReplInvariantErrorType.STORE_TO_PRIMARY_FENCED_AFTER_MEMCPY)
            # check structure addr
            if pm_store.op.stinfo_match:
                if not src_struct_addr:
                    src_struct_addr = pm_store.op.stinfo_match.addr
                elif src_struct_addr != pm_store.op.stinfo_match.addr:
                    self.err_dict[pm_store.op.seq] = ReplInvariantErrorType.STORE_TO_PRIMARY_NOT_IN_SAME_STRUCT
                    err_list.append(ReplInvariantErrorType.STORE_TO_PRIMARY_NOT_IN_SAME_STRUCT)


        # 3. check the data in the primary and the replica are the same
        if ReplInvariantErrorType.STORE_TO_PRIMARY_NOT_IN_SAME_STRUCT in err_list:
            # the stores to the primary are not in the same structure, unable to compare with the replica structure bytes.
            pass
        elif not src_struct_addr:
            # cannot form the source bytes
            pass
        elif not self.store_op.op_st.sv_entry:
            # do not have the store trace record, do we need to report bug?
            # I think not. This may be a tracing issue rather than a file-system issue
            pass
        else:
            # After memcpy, the primary and the replica should have the same content
            # Since one filed may be updated multiple times before memcpy, we cannot directly compare one write with the content fter the memcpy
            # More, since some fields may not be updated, we cannot create a zero bytes to store all writes.
            # Such that we use the old content of the replica as the old content of the primary, and update its content by each write.
            primary_data : bytearray = bytearray(self.store_op.op_st.ov_entry.data)
            replica_data : bytearray = bytearray(self.store_op.op_st.sv_entry.data)
            for pm_store in self.stores_to_primary_replica:
                pm_store : MechPMStoreEntry
                if pm_store.op.sv_entry:
                    offset = pm_store.addr - src_struct_addr
                    primary_data[offset:offset+pm_store.size] = pm_store.op.sv_entry.data
            if primary_data != replica_data:
                if log.debug:
                    hex_primary_data = ' '.join(format(x, '02x') for x in primary_data)
                    hex_replica_data = ' '.join(format(x, '02x') for x in replica_data)
                    msg = f"primary and replica data does not match:\n0x{hex_primary_data}\n0x{hex_replica_data}\n{self.dbg_get_detail()}"
                    log.global_logger.debug(msg)
                self.err_dict[1] = ReplInvariantErrorType.PRIMARY_AND_REPLICA_DATA_NOT_MATCH
                err_list.append(ReplInvariantErrorType.PRIMARY_AND_REPLICA_DATA_NOT_MATCH)

        return err_list

    def dbg_get_detail(self):
        data = ''
        data += "memcpy from pm: \n"
        for load in self.load_op_list:
            data += f"{str(load)}, {load.op_st.src_entry}\n"
        data += f"memcpy to pm:\n{str(self.store_op)}\n"
        if self.store_pmstore:
            data += f"seq: {self.store_op.op_st.seq}, fence seq: {self.store_pmstore.fence_op.seq}, {self.store_op.op_st.stinfo_match}, {self.store_op.op_st.var_list}, {self.store_op.op_st.src_entry}\n"
        else:
            data += f"seq: {self.store_op.op_st.seq}, {self.store_op.op_st.stinfo_match}, {self.store_op.op_st.var_list}, {self.store_op.op_st.src_entry}\n"
        data += f"repl entry invariant check result: {list(self.err_dict.values())}\n"
        data += "store to primary replica: \n"
        for store in self.stores_to_primary_replica:
            store : MechPMStoreEntry
            data += f"seq: {store.op.seq}, fence seq: {store.fence_op.seq}, {store.op.stinfo_match}, {store.op.var_list}, {store.op.src_entry}"
            if store.op.seq in self.err_dict:
                data += f" ({self.err_dict[store.op.seq]})\n"
            else:
                data += "\n"
        return data

    def dbg_print_detail(self):
        print(self.dbg_get_detail())
