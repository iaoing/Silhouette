import os
import sys
import time

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.trace_proc.trace_reader.trace_entry import TraceEntry
from scripts.trace_proc.pm_trace.pm_trace_split import is_pm_entry
from scripts.trace_proc.pm_trace.pm_trace_split import pm_split_seq_entrylist_map
from scripts.cache_sim.witcher.cache.entry_op_conv import convert_seq_entrylist_dict
from scripts.cache_sim.witcher.cache.atomic_op import Store, Flush, Fence
from scripts.cache_sim.witcher.cache.reorder_simulator import ReorderSimulator, get_write_dep_seq_map
from tools.scripts.disk_content.ctx_file_reader import CtxFileReader, DiskEntryAttrs
from scripts.utils.logger import global_logger
import scripts.utils.logger as log
from scripts.utils.utils import isUserSpaceAddr
from scripts.utils.utils import getTimestamp

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.vfs_op.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class OpTraceEntry:
    """ OpTraceEntry represents one operation range (including all ops). """
    def __init__(self, start_fn_entry : TraceEntry, op_name, pm_addr, pm_size, pid):
        dbg_msg = "OpTraceEntry: pm addr range: [0x%x, 0x%x]" % (pm_addr, pm_addr + pm_size)
        global_logger.debug(dbg_msg)

        self.start_fn_entry : TraceEntry = start_fn_entry
        self.end_fn_entry  : TraceEntry = None

        self.op_name = op_name
        self.pm_addr = pm_addr
        self.pm_size = pm_size

        # oracle before and after this op
        self.prev_op_oracle : CtxFileReader = None
        self.post_op_oracle : CtxFileReader = None

        # all entries of the same operation should have the same pid
        self.pid = pid

        # min seq and max seq of entries
        self.min_seq = sys.maxsize
        self.max_seq = -1

        # dict(seq, entry_list)
        self.seq_entry_map = dict()

        self.mem_copy_list = list()
        self.mem_set_list = list()
        self.user_space_trans_load_seq_entry_map = dict()

        # same dict but only pm operations (store, flush, fence)
        self.pm_seq_entry_map = dict()
        self.pm_sorted_seq = []
        # a list of pm store (e.g., store, memcpy, cas) seq
        self.pm_sorted_store_seq = []
        # the id is a list of instruction id in seq order.
        self.pm_op_id = []

        # this is atomic operation list of PM store-related operations
        self.atomic_op_list = []

        # a list of num represents in-fight stores
        # we do not need to know exactly ops, just record number here.
        self.in_fight_store_num = []

        # maps seq to a list of in-flight num. E.g.,
        # seq 1: [1,2,3] which means it exists in in-flight cluster 1, 2, 3 (fenced at 3)
        # seq 2: [2] which means it exists in in-flight cluster 2 (fence at 2)
        self.in_flight_seq_cluster_map = dict()
        # maps from cluster number to a list of seq of in-flight stores
        self.in_flight_cluster_seq_map = dict()
        # maps from cluster number to a list of flushing ops
        # which means the ops will be persisted by the end of this cluster.
        self.in_flight_cluster_flushing_map = dict()

        # maps from seq number to a set of seq numbers
        # used to indicate a set of seq ops must be happen before this key seq
        # E.g., the WAW (overwrite) situation, the fence stores.
        # the write and deps are in the same in-flight cluster.
        self.write_dep_seq_map = dict()

        # number of crash plan dict
        # the key is the fence seq
        # the value is a tuple: {num of crash plans, number of in-flight stores, num of computed in flight stores}
        self.num_cps_map = dict()

        # unflushed stores
        self.unflushed_stores = []
        # duplicated flushes
        self.dup_flushes = []
        # duplicated fences
        self.dup_fences = []

        self.reorder_simulator : ReorderSimulator = None

    def get_op_list_by_seq(self, seq):
        if seq in self.seq_entry_map:
            return self.seq_entry_map[seq]
        return None

    def get_pm_op_list_by_seq(self, seq):
        if seq in self.pm_seq_entry_map:
            return self.pm_seq_entry_map[seq]
        return None

    def get_pm_ops_by_seq_range(self, seq1, seq2):
        '''return a list of a list of entries'''
        rst = []
        for seq, entry_list in self.pm_seq_entry_map.items():
            if seq1 <= seq <= seq2:
                rst.append(entry_list)
        return rst

    def get_pm_ops_by_addr_range(self, addr1, addr2):
        '''return a list of a list of entries'''
        rst = []
        for seq, entry_list in self.pm_seq_entry_map.items():
            for entry in entry_list:
                entry : TraceEntry
                if addr1 <= entry.addr and entry.addr + entry.size <= addr2:
                    rst.append(entry)
        return rst

    def get_pm_ops_by_seq_addr_range(self, seq1, seq2, addr1, addr2):
        '''return a list of a list of entries'''
        rst = []
        for seq, entry_list in self.pm_seq_entry_map.items():
            if seq < seq1 or seq2 < seq:
                continue
            for entry in entry_list:
                entry : TraceEntry
                if addr1 <= entry.addr and entry.addr + entry.size <= addr2:
                    rst.append(entry)
        return rst

    def add_entry_list(self, entry_list, add_to_pm):
        entry = entry_list[0]
        entry : TraceEntry
        assert self.pid == entry.pid, "mismatched pid, %d, %s" % (self.pid, entry.raw_line)
        assert entry.seq not in self.seq_entry_map, "seq [%d] is afeard in the map" % (entry.seq)

        self.min_seq = min(self.min_seq, entry.seq)
        self.max_seq = max(self.max_seq, entry.seq)
        self.seq_entry_map[entry.seq] = entry_list

        if entry.type.isMemTransLoad() and isUserSpaceAddr(entry.addr):
            global_logger.debug("mem trans load addr: %d" % (entry.seq))
            self.user_space_trans_load_seq_entry_map[entry.seq] = entry_list

        if entry.type.isMemTransStore() and is_pm_entry(entry, self.pm_addr, self.pm_size):
            self.mem_copy_list.append(entry)
        if entry.type.isMemset() and is_pm_entry(entry, self.pm_addr, self.pm_size):
            self.mem_set_list.append(entry)

        if add_to_pm and is_pm_entry(entry, self.pm_addr, self.pm_size):
            self.pm_seq_entry_map[entry.seq] = entry_list

    def init_pm_entries(self):
        '''Even we could add entries to pm in adding, we still provide an function to rebuild pm map in needed'''
        self.pm_seq_entry_map = pm_split_seq_entrylist_map(self.seq_entry_map, self.pm_addr, self.pm_size)

    def finalize(self):
        self.pm_sorted_seq = []
        self.pm_op_id = []
        for seq, entry_list in sorted(self.pm_seq_entry_map.items()):
            self.pm_sorted_seq.append(seq)
            self.pm_op_id.append(entry_list[0].instid)
            if entry_list[0].type.isStoreSeries():
                self.pm_sorted_store_seq.append(entry_list[0].seq)
        # global_logger.debug("PM op id length: %d" % (len(self.pm_op_id)))

    @timeit
    def convert_atomic_ops(self, ignore_nonatomic_write : bool,
                               nonatomic_as_one : bool,
                               sampling_nonatomic_write : bool, force):
        if force == True or \
                (len(self.atomic_op_list) == 0 and len(self.pm_seq_entry_map) > 0):
            self.atomic_op_list = []
            self.atomic_op_list = convert_seq_entrylist_dict(self.pm_seq_entry_map, \
                                                             ignore_nonatomic_write, \
                                                             nonatomic_as_one, \
                                                             sampling_nonatomic_write)
            global_logger.info("atomic op list length: %d" % (len(self.atomic_op_list)))

    @timeit
    def analysis_in_cache_run(self, cache, ignore_nonatomic_write : bool,
                               nonatomic_as_one : bool,
                               sampling_nonatomic_write : bool,
                                    force=False):
        if len(self.atomic_op_list) == 0 and len(self.pm_seq_entry_map) > 0:
            self.convert_atomic_ops(ignore_nonatomic_write=ignore_nonatomic_write,
                                    nonatomic_as_one=nonatomic_as_one,
                                    sampling_nonatomic_write=sampling_nonatomic_write,
                                    force=force)

        self.reorder_simulator = ReorderSimulator(cache, consider_ow=True)
        self.in_fight_store_num = []
        self.in_flight_seq_cluster_map = dict()
        self.in_flight_cluster_seq_map = dict()
        self.in_flight_cluster_flushing_map = dict()
        in_flight_cluster_num = 0
        for op in self.atomic_op_list:
            if isinstance(op, Store):
                cache.accept(op)
            elif isinstance(op, Flush):
                cache.accept(op)
            elif isinstance(op, Fence):
                self.in_fight_store_num.append(cache.get_in_fight_nums())
                if self.reorder_simulator:
                    self.num_cps_map[op.seq] = self.reorder_simulator.get_reorder_nums()

                tmp_dep_map = get_write_dep_seq_map(cache)
                for k_seq, v_set in tmp_dep_map.items():
                    if k_seq not in self.write_dep_seq_map:
                        self.write_dep_seq_map[k_seq] = set()
                    self.write_dep_seq_map[k_seq] |= v_set

                in_flight_cluster_num += 1
                self.in_flight_cluster_seq_map[in_flight_cluster_num] = []
                self.in_flight_cluster_flushing_map[in_flight_cluster_num] = [x.seq for x in cache.get_all_flushing_ops()]
                for op in cache.get_in_fight_ops():
                    self.in_flight_cluster_seq_map[in_flight_cluster_num].append(op.seq)
                    if op.seq not in self.in_flight_seq_cluster_map:
                        self.in_flight_seq_cluster_map[op.seq] = []
                    self.in_flight_seq_cluster_map[op.seq].append(in_flight_cluster_num)

                cache.accept(op)
                cache.write_back_all_flushing_stores()
                cache.write_back_all_persisted_stores()
            else:
                assert False, "invalid op type, %s, %s" % (type(op), str(op))

        # the last ops that still in cache
        tmp_dep_map = get_write_dep_seq_map(cache)
        for k_seq, v_set in tmp_dep_map.items():
            if k_seq not in self.write_dep_seq_map:
                self.write_dep_seq_map[k_seq] = set()
            self.write_dep_seq_map[k_seq] |= v_set

        in_flight_cluster_num += 1
        self.in_flight_cluster_seq_map[in_flight_cluster_num] = []
        self.in_flight_cluster_flushing_map[in_flight_cluster_num] = [x.seq for x in cache.get_all_flushing_ops()]
        for op in cache.get_in_fight_ops():
            self.in_flight_cluster_seq_map[in_flight_cluster_num].append(op.seq)
            if op.seq not in self.in_flight_seq_cluster_map:
                self.in_flight_seq_cluster_map[op.seq] = []
            self.in_flight_seq_cluster_map[op.seq].append(in_flight_cluster_num)

        # Q: do we need to flush all stores at the end of the function?
        # A: yes, the end of VFS op triggers a context switch, which implies a fence
        self.in_fight_store_num.append(cache.get_in_fight_nums())
        if self.reorder_simulator:
            self.num_cps_map[sys.maxsize] = self.reorder_simulator.get_reorder_nums()
        cache.write_back_all_flushing_stores()

        in_flight_cluster_num += 1
        self.in_flight_cluster_seq_map[in_flight_cluster_num] = [x.seq for x in cache.get_in_fight_ops()]
        self.in_flight_cluster_flushing_map[in_flight_cluster_num] = [x.seq for x in cache.get_in_fight_ops()]

        self.dup_fences = cache.dup_fence_list
        self.dup_flushes = cache.dup_flush_list
        if self.in_fight_store_num[-1] > 0:
            self.unflushed_stores = cache.get_in_fight_ops()

        global_logger.info("number of in-fight stores %d" % (len(self.in_fight_store_num)))
        global_logger.info("number of duplicated flushes %d" % (len(self.dup_flushes)))
        global_logger.info("number of duplicated fences %d" % (len(self.dup_fences)))
        global_logger.info("number of unflushed stores %d" % (len(self.unflushed_stores)))
        global_logger.info("in-fight stores: %s" % (self.in_fight_store_num.__str__()))
        global_logger.info("duplicated flushes: %s" % (self.dup_flushes.__str__()))
        global_logger.info("duplicated fences: %s" % (self.dup_fences.__str__()))
        global_logger.info("unflushed stores: %s" % (self.unflushed_stores.__str__()))
        global_logger.info("write dep seq map: %s" % (str(self.write_dep_seq_map)))

    def get_cache_analysis_result(self) -> str:
        def helper(lst):
            data = ""
            for atomic_op in lst:
                seq = atomic_op.seq
                entry_list = self.get_pm_op_list_by_seq(seq)
                entry = entry_list[0]
                data += "%s, %s\n" % (str(atomic_op), entry.to_result_str())
            return data

        def helper_nest(lst):
            num = 0
            data = ""
            for nest_lst in lst:
                num += 1
                data += "#%d:\n" % (num)
                for atomic_op in nest_lst:
                    seq = atomic_op.seq
                    entry_list = self.get_pm_op_list_by_seq(seq)
                    entry = entry_list[0]
                    data += "%s, %s\n" % (str(atomic_op), entry.to_result_str())
            return data

        data = "#### cache analysis result: " + self.op_name + "\n"
        data += "## in-flight store number list:\n%s\n" % (str(self.in_fight_store_num))
        data += "## the number of crash plans: \n"
        for seq, tu in sorted(self.num_cps_map.items()):
            data += "%d: %d, %d, %d; " % (seq, tu[0], tu[1], tu[2])
        data += "\n"

        data += "## the number of memory copies: %d\n" % (len(self.mem_copy_list))
        for e in self.mem_copy_list:
            e : TraceEntry
            data += "%d,%s,%d;" % (e.seq, hex(e.addr), e.size)
        data += "\n"
        data += "## the number of memory sets: %d\n" % (len(self.mem_set_list))
        for e in self.mem_set_list:
            e : TraceEntry
            data += "%d,%s,%d;" % (e.seq, hex(e.addr), e.size)
        data += "\n"

        data += "## duplicate flushes: %d\n" % (len(self.dup_flushes))
        data += helper_nest(self.dup_flushes)
        data += "## duplicate fences: %d\n" % (len(self.dup_fences))
        data += helper_nest(self.dup_fences)
        data += "## unflushed stores: %d\n" % (len(self.unflushed_stores))
        data += helper(self.unflushed_stores)
        return data

    def debug_print_all(self):
        for seq, entry_list in sorted(self.seq_entry_map.items()):
            print(entry_list[0])

    def debug_print_all_pm(self):
        for seq, entry_list in sorted(self.pm_seq_entry_map.items()):
            print(entry_list[0])

    def debug_print_brief(self):
        print("%d entry list in map, %d entry list in pm map" % (len(self.seq_entry_map), len(self.pm_seq_entry_map)))
        print(self.start_fn_entry)
        print(self.end_fn_entry)
