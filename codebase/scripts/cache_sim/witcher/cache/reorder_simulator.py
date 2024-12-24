import os
import sys
import time
from itertools import combinations

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.cache_sim.witcher.cache.atomic_op import Store, Flush, Fence
from scripts.cache_sim.witcher.cache.witcher_cache import WitcherCache, WitcherCacheline
from scripts.utils.const_var import CACHELINE_BYTES
from scripts.utils.const_var import ATOMIC_WRITE_BYTES
from scripts.utils.utils import alignToFloor, alignToCeil
from scripts.utils.logger import global_logger
import scripts.utils.logger as log

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.guest.reorder_sim.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper

class ReorderCacheLine():
    """Only for the use of computing number of valid order"""
    def __init__(self, op_list):
        """op_list: a list of atomic store operations that in the same fence range"""
        self.op_list = op_list
        # maps the overwrite to a list of the number of overwrites.
        # overwrite indicate how many stores have dependencies
        self.overwrite_map = dict()
        self.__init_ow_map()

    def __init_ow_map(self):
        # split cache line into 8 bytes slots to check overwrites
        atomic_slots = [0 for x in range(CACHELINE_BYTES//ATOMIC_WRITE_BYTES)]
        for op in self.op_list:
            slot = (op.addr % CACHELINE_BYTES)//ATOMIC_WRITE_BYTES
            atomic_slots[slot] += 1
        for slot in range(len(atomic_slots)):
            ows = atomic_slots[slot]
            if ows < 2:
                continue
            if ows not in self.overwrite_map:
                self.overwrite_map[ows] = 0
            self.overwrite_map[ows] += 1

    def get_combinatorial_num(self, allow_none : bool, consider_ow : bool) -> int:
        """
        allow_none: allow selecting none of writes (C_n^0)
        consider_ow: consider the overwrite dependencies
        """
        if not consider_ow:
            rst = pow(2, len(self.op_list))
            if allow_none:
                return rst
            else:
                return rst - 1
        else:
            num_ow_stores = 0
            num_ow_stores_plus_1 = 1
            for ows, cnt in self.overwrite_map.items():
                num_ow_stores += ows * cnt
                num_ow_stores_plus_1 *= (pow(ows+1, cnt))
            assert len(self.op_list) >= num_ow_stores, \
                "number of overwrite stores are larger than the number of ops: %d, %d" \
                % (num_ow_stores, len(self.op_list))

            rst = num_ow_stores_plus_1 * pow(2, len(self.op_list) - num_ow_stores)
            if allow_none:
                return rst
            else:
                return rst - 1

def get_write_dep_seq_map(cache : WitcherCache):
    rst = dict()

    # for fenced dep
    for cacheline in cache.get_cachelines():
        cacheline : WitcherCacheline
        tmp = dict()
        for op in cacheline.stores_list:
            op : Store
            if len(op.fence_list) not in tmp:
                tmp[len(op.fence_list)] = set()
            tmp[len(op.fence_list)].add(op)
        last_ops = set()
        for _, op_set in sorted(tmp.items()):
            for op in op_set:
                if op.seq not in rst:
                    rst[op.seq] = set()
                rst[op.seq] |= last_ops
            last_ops |= op_set

    # for overwrites
    for cacheline in cache.get_cachelines():
        cacheline : WitcherCacheline
        tmp = dict()
        for op in cacheline.stores_list:
            atomic_slots = (op.addr % CACHELINE_BYTES)//ATOMIC_WRITE_BYTES
            if atomic_slots not in tmp:
                tmp[atomic_slots] = list()
            tmp[atomic_slots].append(op)
        for _, op_list in tmp.items():
            op_list.sort(key=lambda x:x.seq)
            last_ops = set()
            for op in op_list:
                if op.seq not in rst:
                    rst[op.seq] = set()
                rst[op.seq] |= last_ops
                last_ops.add(op)

    # normalize to save space
    normalized_rst = dict()
    for seq, op_set in rst.items():
        if len(op_set) == 0:
            continue
        seq_set = set(x.seq for x in op_set)
        if seq in seq_set:
            seq_set.remove(seq)
        if len(seq_set) == 0:
            continue
        normalized_rst[seq] = seq_set

    return normalized_rst

def get_reorder_num_of_one_cacheline(op_list, allow_none : bool, consider_ow : bool):
    if len(op_list) == 0:
        return -1
    rcl = ReorderCacheLine(op_list)
    return rcl.get_combinatorial_num(allow_none, consider_ow)

class ReorderSimulator():
    """The simulator for reordering stores."""
    def __init__(self, cache : WitcherCache, consider_ow : bool):
        self.cache = cache
        self.consider_ow = consider_ow

    def __get_reorder_nums_no_dep(self,
                                  prev_fence_non_dep_cachelines,
                                  post_fence_non_dep_cachelines):
        # 1. select at least one store from post-fence non-dep stores *
        #    the combination of pre-fence stores
        tmp_list = []
        for addr, ops in post_fence_non_dep_cachelines.items():
            tmp_list.append(get_reorder_num_of_one_cacheline(ops, True, self.consider_ow))
        num_cps_case_1 = 0
        for i in range(len(tmp_list)):
            # select at least one store from i, and combination of the rest of stores
            tmp_num = tmp_list[i] - 1
            if tmp_num > 0:
                for j in range(len(tmp_list)):
                    if i == j:
                        continue
                    tmp_num *= tmp_list[j]
                num_cps_case_1 += tmp_num
        for addr, ops in prev_fence_non_dep_cachelines.items():
            if len(ops) > 0:
                num_cps_case_1 *= get_reorder_num_of_one_cacheline(ops, True, self.consider_ow)

        return num_cps_case_1

    def __get_reorder_nums(self,
                           prev_fence_dep_cachelines,
                           prev_fence_non_dep_cachelines,
                           post_fence_dep_cachelines,
                           post_fence_non_dep_cachelines,
                           memo : dict):
        """
        memo: the memorized number of crash plans of a sub case cachelines.
              E.g., two dep cachelines with all non-dep cachelines.
              Since sub-cases should contains all non-dep cachelines,
              we can use the info of prev and post fence dep cachelines as  the key.
              The key is is a tuple of the cacheline addresses, i.e.,
              {cacheline_1_addr, cacheline_2_addr, ..., cacheline_n_addr}
        """
        assert len(prev_fence_dep_cachelines) == len(post_fence_dep_cachelines), \
            "mismatched prev and post dep cachelines, %d, %d" \
                % (len(prev_fence_dep_cachelines), len(post_fence_dep_cachelines))

        global_logger.debug("prev_fence_dep_cachelines: %s" % (prev_fence_dep_cachelines))
        global_logger.debug("post_fence_dep_cachelines: %s" % (post_fence_dep_cachelines))
        global_logger.debug("prev_fence_non_dep_cachelines: %s" % (prev_fence_non_dep_cachelines))
        global_logger.debug("post_fence_non_dep_cachelines: %s" % (post_fence_non_dep_cachelines))
        global_logger.debug("memo: %s" % (str(memo)))

        # 1. select at least one store from post-fence non-dep stores *
        #    the combination of pre-fence stores
        tmp_list = []
        for addr, ops in post_fence_non_dep_cachelines.items():
            tmp_list.append(get_reorder_num_of_one_cacheline(ops, True, self.consider_ow))
        num_cps_case_1 = 0
        for i in range(len(tmp_list)):
            # select at least one store from i, and combination of the rest of stores
            tmp_num = tmp_list[i] - 1
            if tmp_num > 0:
                for j in range(len(tmp_list)):
                    if i == j:
                        continue
                    tmp_num *= tmp_list[j]
                num_cps_case_1 += tmp_num
        for addr, ops in prev_fence_dep_cachelines.items():
            if len(ops) > 0:
                num_cps_case_1 *= get_reorder_num_of_one_cacheline(ops, True, self.consider_ow)
        for addr, ops in prev_fence_non_dep_cachelines.items():
            if len(ops) > 0:
                num_cps_case_1 *= get_reorder_num_of_one_cacheline(ops, True, self.consider_ow)

        # 2. select at least one store from each post-fence dep store cacheline *
        #    the combination of both prev and post fence non-dep stores.
        num_cps_case_2 = 1
        for addr, ops in post_fence_dep_cachelines.items():
            if len(ops) > 0:
                num_cps_case_2 *= get_reorder_num_of_one_cacheline(ops, False, self.consider_ow)
        for addr, ops in prev_fence_non_dep_cachelines.items():
            if len(ops) > 0:
                num_cps_case_2 *= get_reorder_num_of_one_cacheline(ops, True, self.consider_ow)
        for addr, ops in post_fence_non_dep_cachelines.items():
            if len(ops) > 0:
                num_cps_case_2 *= get_reorder_num_of_one_cacheline(ops, True, self.consider_ow)

        # 3. calculate the number of crash plans of selecting i (i >= 1) dep cachelines and
        #    all non-dep stores
        num_cps_case_3 = 0
        dep_cacheline_addr_list = [x for x in post_fence_dep_cachelines.keys()]
        for i in range(1, len(post_fence_dep_cachelines)):
            combo_list = list(combinations(dep_cacheline_addr_list, i))
            for combo in combo_list:
                if combo not in memo:
                    new_prev_fence_dep_cachelines = {key: prev_fence_dep_cachelines[key] for key in combo}
                    new_post_fence_dep_cachelines = {key: post_fence_dep_cachelines[key] for key in combo}
                    memo[combo] = self.__get_reorder_nums(new_prev_fence_dep_cachelines,
                                                          prev_fence_non_dep_cachelines,
                                                          new_post_fence_dep_cachelines,
                                                          post_fence_non_dep_cachelines,
                                                          memo)
                num_cps_case_3 += memo[combo]
        global_logger.debug("case 1: %d, case 2: %d, case 3: %d" % (num_cps_case_1, num_cps_case_2, num_cps_case_3))

        # 4. calculate the total number
        total_number_crash_plans = num_cps_case_1 + num_cps_case_2 + num_cps_case_3
        # for combo, num in memo.items():
        #     # 4.1 select at least one store from the dep cachelines that are not in combo *
        #     #     the number of crash plans of the combo
        #     num_cps_case_4_1 = num
        #     rest_dep_cacheline_addr_list = [x for x in dep_cacheline_addr_list if x not in combo]
        #     for addr in rest_dep_cacheline_addr_list:
        #         op_list = post_fence_dep_cachelines[addr]
        #         num_cps_case_4_1 *= get_reorder_num_of_one_cacheline(op_list, False, True)
        #     total_number_crash_plans += num_cps_case_4_1

        return total_number_crash_plans

    # @timeit
    # do not timing it since the elapsed time is ~32 macroseconds, which is less than the time to send msg to the server (~140 macroseconds).
    def get_reorder_nums(self):
        '''
        Request: call this method BEFORE processing a fence op. For example,
        if (op is fence):
            get_reorder_nums()
        cache.accept(op)
        Case:
        B: barrier; F: flush; m, n, p, q: the number of stores
        | m | B | p | F |
        | n | B |   | F |
        |   | B | q | F |
        Number of CPs:
        Refer to the slides.
        This function only process the last two fenced regions, it does not
        consider any stores before the second to last fence.
        '''
        num_cachelines = len(self.cache.cacheline_dict)

        # cachelines are stored in a dict,
        # the key is the cacheline address, the value is a list of ops.
        prev_fence_cachelines = dict()
        post_fence_cachelines = dict()
        prev_fence_dep_cachelines = dict()
        prev_fence_non_dep_cachelines = dict()
        post_fence_dep_cachelines = dict()
        post_fence_non_dep_cachelines = dict()
        for cacheline in self.cache.get_cachelines():
            cacheline : WitcherCacheline
            addr = cacheline.address
            prev_fence_cachelines[addr] = []
            post_fence_cachelines[addr] = []
            for store in cacheline.stores_list:
                store : Store
                if len(store.fence_list) == 1:
                    # fenced by the lastest fence
                    prev_fence_cachelines[addr].append(store)
                elif len(store.fence_list) == 0:
                    # the store occurs after the lastest fence
                    post_fence_cachelines[addr].append(store)
                else:
                    # the store occurs far before the lastest fence
                    # we do not need to consider them, since they cannot be reordered.
                    pass

        global_logger.debug("prev_fence_cachelines: %s" % (prev_fence_cachelines))
        global_logger.debug("post_fence_cachelines: %s" % (post_fence_cachelines))

        for cacheline in self.cache.get_cachelines():
            cacheline : WitcherCacheline
            addr = cacheline.address
            if len(prev_fence_cachelines[addr]) == 0:
                # no prev fence stores for this post fence stores
                post_fence_non_dep_cachelines[addr] = post_fence_cachelines[addr]
            else:
                if len(post_fence_cachelines[addr]) == 0:
                    # no post fence stores for this prev fence stores
                    prev_fence_non_dep_cachelines[addr] = prev_fence_cachelines[addr]
                else:
                    prev_fence_dep_cachelines[addr] = prev_fence_cachelines[addr]
                    post_fence_dep_cachelines[addr] = post_fence_cachelines[addr]
            if len(post_fence_cachelines[addr]) == 0:
                # no post fence stores for this prev fence stores
                prev_fence_non_dep_cachelines[addr] = prev_fence_cachelines[addr]
            else:
                if len(prev_fence_cachelines[addr]) == 0:
                    # no prev fence stores for this post fence stores
                    post_fence_non_dep_cachelines[addr] = post_fence_cachelines[addr]
                else:
                    prev_fence_dep_cachelines[addr] = prev_fence_cachelines[addr]
                    post_fence_dep_cachelines[addr] = post_fence_cachelines[addr]

        global_logger.debug("prev_fence_dep_cachelines: %s" % (prev_fence_dep_cachelines))
        global_logger.debug("post_fence_dep_cachelines: %s" % (post_fence_dep_cachelines))
        global_logger.debug("prev_fence_non_dep_cachelines: %s" % (prev_fence_non_dep_cachelines))
        global_logger.debug("post_fence_non_dep_cachelines: %s" % (post_fence_non_dep_cachelines))

        rst = -1
        if len(prev_fence_dep_cachelines) == 0:
            rst = self.__get_reorder_nums_no_dep(prev_fence_non_dep_cachelines,
                                                 post_fence_non_dep_cachelines)
        else:
            memo = dict()
            rst = self.__get_reorder_nums(prev_fence_dep_cachelines,
                                        prev_fence_non_dep_cachelines,
                                        post_fence_dep_cachelines,
                                        post_fence_non_dep_cachelines,
                                        memo)
            global_logger.debug(str(memo))

        s1 = sum([len(x) for x in prev_fence_dep_cachelines.values()])
        s2 = sum([len(x) for x in post_fence_dep_cachelines.values()])
        s3 = sum([len(x) for x in prev_fence_non_dep_cachelines.values()])
        s4 = sum([len(x) for x in post_fence_non_dep_cachelines.values()])
        s1 = 99999999999999999999 if s1 > 99999999999999999999 else s1
        s2 = 99999999999999999999 if s2 > 99999999999999999999 else s2
        s3 = 99999999999999999999 if s3 > 99999999999999999999 else s3
        s4 = 99999999999999999999 if s4 > 99999999999999999999 else s4
        rst = 99999999999999999999 if rst > 99999999999999999999 else rst
        global_logger.debug("number of crash plans: %d, %d, %d, %d, %d" % \
                            (s1, s2, s3, s4, rst))

        num_in_flight_stores = self.cache.get_in_fight_nums()
        num_computed_in_flight_stores = sum([len(x) for x in prev_fence_cachelines.values()]) \
                                      + sum([len(x) for x in post_fence_cachelines.values()])

        return rst, num_in_flight_stores, num_computed_in_flight_stores

    def __get_reorder_nums_v2(self,
                              fence_cachelines : dict,
                              memo : dict):
        pass

    @timeit
    def get_reorder_nums_v2(self):
        '''
        Request: call this method BEFORE processing a fence op. For example,
        if (op is fence):
            get_reorder_nums()
        cache.accept(op)
        Case:
        B: barrier; F: flush; m, n, p, q: the number of stores
        | m | B | p | F | B |
        | n | B |   | F | B |
        |   | B | q | F | B |
        Number of CPs:
        Refer to the slides.
        This function consider all stores in any fenced region.
        '''

        # cachelines are stored in a dict in three dimension,
        # the 1st key is the fence seq, the value is a dict,
        # the 2nd key is the cacheline address, the value is a list of ops.
        fence_cachelines = dict()
        max_fence_seq = sys.maxsize
        for cacheline in self.cache.get_cachelines():
            cacheline : WitcherCacheline
            cl_addr = cacheline.address
            for store in cacheline.stores_list:
                store : Store
                fence_seq = max_fence_seq
                if len(store.fence_list) > 0:
                    fence_seq = store.fence_list[0].seq
                if fence_seq not in fence_cachelines:
                    fence_cachelines[fence_seq] = dict()
                if cl_addr not in fence_cachelines[fence_seq]:
                    fence_cachelines[fence_seq][cl_addr] = []
                fence_cachelines[fence_seq][cl_addr].append(store)

        # the key of the memo is tuple('fence:seq', cl_addr1, cl_addr2, ...)
        # the value is the number of crash plans of two fenced regions before the fence seq.
        # E.g.,
        # cl1  s1, fence1, s3, fence2, s5, fence3
        # cl2  s2, fence1, s4, fence2, s6, fence3
        # The investigated stores are s1 and s2 if the fence seq is fence1
        # The investigated stores are s1, s2, s3 and s4 if the fence seq is fence2
        # The investigated stores are s3, s4, s5 and s6 if the fence seq is fence3
        memo = dict()
        rst = self.__get_reorder_nums_v2(fence_cachelines, memo)
        global_logger.debug(str(memo))
        return rst

class CacheLineReorderSimulator():
    """
    The simulator for reordering cache lines.
    Stores inside cache lines will not be reordered.
    """
    def __init__(self, cache : WitcherCache):
        self.cache = cache

    def get_reorder_nums(self):
        num_cachelines = len(self.cache.cacheline_dict)
        return (2**num_cachelines - 1)

    def get_reorder_crash_plan_list(self):
        """
        Returns a list that contains crash plans.
        Each crash plan contains a list of seqs that need to be persisted.
        """
        rst = []
        cacheline_seq_list = []
        for cacheline in self.cache.get_cachelines():
            if len(cacheline.stores_list) > 0:
                cacheline_seq_list.append([x.seq for x in cacheline.stores_list])
        for i in range(1, len(cacheline_seq_list) + 1):
            for tu in combinations(cacheline_seq_list, i):
                rst.append([])
                for cl_seq in tu:
                    rst[-1] += cl_seq

        return rst