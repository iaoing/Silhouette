import os
import sys
import logging
from itertools import combinations

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(codebase_dir)

from scripts.cache_sim.witcher.cache.atomic_op import Store, Flush, Fence
from scripts.cache_sim.witcher.cache.witcher_cache import WitcherCache, WitcherCacheline
from scripts.cache_sim.witcher.cache.reorder_simulator import ReorderSimulator
from scripts.cache_sim.witcher.binary_file.binary_file import EmptyBinaryFile
from scripts.utils.const_var import CACHELINE_BYTES
from scripts.utils.const_var import ATOMIC_WRITE_BYTES
from scripts.utils.utils import alignToFloor, alignToCeil
from scripts.utils.logger import global_logger, setup_global_logger

def init_log():
    setup_global_logger(stm = sys.stderr, stm_lv=logging.DEBUG)

def get_passed_str():
    return '\033[92m' + 'passed' + '\033[0m'

def get_failed_str():
    return '\033[91m' + 'failed' + '\033[0m'

def gen_stores(addr, seq, num_non_ows, num_ows : dict) -> list:
    """
    If the number of stores exceeds some number, they must have overwrites.
    """
    store_list = []
    store_seq = seq
    store_addr = addr
    store_size = ATOMIC_WRITE_BYTES
    for ows, num in num_ows.items():
        for i in range(num):
            for j in range(ows):
                assert store_addr < addr + CACHELINE_BYTES, "too much overwrites!"
                store_list.append(Store(store_seq, store_addr, store_size))
                store_seq += 1
            store_addr += ATOMIC_WRITE_BYTES

    for i in range(num_non_ows):
        assert store_addr < addr + CACHELINE_BYTES, "too much stores!"
        store_list.append(Store(store_seq, store_addr, store_size))
        store_seq += 1
        store_addr += ATOMIC_WRITE_BYTES

    global_logger.debug("generate stores %s for %d non-ow stores and %s ows" \
                        % (str(store_list), num_non_ows, str(num_ows)))

    return store_list

def gen_num_crash_plans(op_list):
    op_list.sort(key = lambda x: x.seq)
    cache = WitcherCache(EmptyBinaryFile())
    simulator = ReorderSimulator(cache, consider_ow = True)

    num_cps = -1
    for op in op_list:
        if isinstance(op, Fence):
            num_cps, num_in_flight_stores, num_computed_in_flight_stores = simulator.get_reorder_nums()
            global_logger.info("number of in-flight stores: %d" % (num_in_flight_stores))
            global_logger.info("number of computed in-flight stores: %d" % (num_computed_in_flight_stores))
            global_logger.info("number of crash plans: %d" % (num_cps))
        cache.accept(op)

    global_logger.info("finally: number of crash plans: %d" % (num_cps))

    return num_cps

"""
The naming rule of the test function:
test_num1_num2_num3_case_num4
num1: the number of dep cachelines
num2: the number of prev-fence non-dep cachelines
num3: the number of post-fence non-dep cachelines
num4: different cases (e.g., number of stores of each cacheline, number of overwrites)
"""

def test_1_0_0_case_1():
    """
    Cacheline 1: prev 1 store, post 1 store
    """
    op_list = []
    cl1_addr = 0

    cl1_prev_seq = 1
    num_non_ows = 1
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 1
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 1:
        global_logger.info("test_1_0_0_case_1: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_0_0_case_1: %s" % (get_failed_str()))

def test_1_0_0_case_2():
    """
    Cacheline 1: prev 1 store, post 2 store
    """
    op_list = []
    cl1_addr = 0

    cl1_prev_seq = 1
    num_non_ows = 1
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 3:
        global_logger.info("test_1_0_0_case_2: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_0_0_case_2: %s" % (get_failed_str()))

def test_1_0_0_case_3():
    """
    Cacheline 1: prev 2 store, post 2 store
    """
    op_list = []
    cl1_addr = 0

    cl1_prev_seq = 1
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 3:
        global_logger.info("test_1_0_0_case_3: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_0_0_case_3: %s" % (get_failed_str()))

def test_1_0_0_case_4():
    """
    Cacheline 1: prev 2 store, post 5 store
    """
    op_list = []
    cl1_addr = 0

    cl1_prev_seq = 1
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 5
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 31:
        global_logger.info("test_1_0_0_case_4: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_0_0_case_4: %s" % (get_failed_str()))

def test_1_0_0_case_5():
    """
    Cacheline 1: prev 4 store, post 6 store
    """
    op_list = []
    cl1_addr = 0

    cl1_prev_seq = 1
    num_non_ows = 4
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 6
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 63:
        global_logger.info("test_1_0_0_case_5: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_0_0_case_5: %s" % (get_failed_str()))

def test_1_1_0_case_1():
    """
    Cacheline 1: 2 pre-fence dep stores, 3 post-fence dep stores,
    Cacheline 2: 4 pre-fence non-dep
    exp number of cps: (2^3 - 1)*(2^4) = 112
    """
    op_list = []

    cl1_addr = 0
    cl1_prev_seq = 1
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    cl2_addr = cl1_addr + CACHELINE_BYTES
    cl2_prev_seq = cl1_prev_seq + 100
    num_non_ows = 4
    num_ows = dict()
    op_list += gen_stores(cl2_addr, cl2_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 3
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 112:
        global_logger.info("test_1_1_0_case_1: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_1_0_case_1: %s" % (get_failed_str()))

def test_1_0_1_case_1():
    """
    Cacheline 1: 2 pre-fence dep stores, 3 post-fence dep stores,
    Cacheline 2: 4 post-fence non-dep stores
    number of crash plans: (2^4 - 1)*(2^2) + (2^3 - 1)*(2^4) = 172
    """
    op_list = []

    cl1_addr = 0
    cl1_prev_seq = 1
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 3
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    cl2_addr = cl1_addr + CACHELINE_BYTES
    cl2_post_seq = cl1_post_seq + 100
    num_non_ows = 4
    num_ows = dict()
    op_list += gen_stores(cl2_addr, cl2_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 172:
        # (2^5 - 1)*(2^(2+4)) + (2^3 - 1)*(2^(4+5))
        global_logger.info("test_1_0_1_case_1: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_0_1_case_1: %s" % (get_failed_str()))

def test_1_1_1_case_1():
    """
    Cacheline 1: 2 pre-fence dep stores, 3 post-fence dep stores,
    Cacheline 2: 4 pre-fence non-dep stores
    Cacheline 3: 5 post-fence non-dep stores
    number of crash plans: (2^5 - 1)*(2^(2+4)) + (2^3 - 1)*(2^(4+5)) = 1984+3584 = 5568
    """
    op_list = []

    cl1_addr = 0
    cl1_prev_seq = 1
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_prev_seq, num_non_ows, num_ows)

    cl2_addr = cl1_addr + CACHELINE_BYTES
    cl2_prev_seq = cl1_prev_seq + 100
    num_non_ows = 4
    num_ows = dict()
    op_list += gen_stores(cl2_addr, cl2_prev_seq, num_non_ows, num_ows)

    fence_seq = 10000
    fence = Fence(fence_seq)
    op_list.append(fence)

    cl1_post_seq = 20000
    num_non_ows = 3
    num_ows = dict()
    op_list += gen_stores(cl1_addr, cl1_post_seq, num_non_ows, num_ows)

    cl3_addr = cl2_addr + CACHELINE_BYTES
    cl3_post_seq = cl1_post_seq + 100
    num_non_ows = 5
    num_ows = dict()
    op_list += gen_stores(cl3_addr, cl3_post_seq, num_non_ows, num_ows)

    fence_seq = 30000
    fence = Fence(fence_seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 5568:
        global_logger.info("test_1_1_1_case_1: %s" % (get_passed_str()))
    else:
        global_logger.info("test_1_1_1_case_1: %s" % (get_failed_str()))

def test_2_1_1_case_1():
    """
    Cacheline 1: 2 pre-fence dep stores, 3 post-fence dep stores,
    Cacheline 2: 4 pre-fence non-dep stores
    Cacheline 3:                         5 post-fence non-dep stores
    Cacheline 4: 3 pre-fence dep stores, 2 post-fence dep stores
    the number of crash plans:
    = (2^5 -1)*(2^(2+4+3)) + (2^3 - 1)*(2^2 - 1)*(2^(4+5)) +
      [(2^5 -1)*(2^(2+4)) + (2^3 - 1)*(2^(4+5))] +
      [(2^5 -1)*(2^(3+4)) + (2^2 - 1)*(2^(4+5))]
    = 31*512 + 7*3*512 + [31*64 + 7*512] + [31*128 + 3*512]
    = 15872 + 10752 + 5568 + 5504
    = 37696
    """
    op_list = []

    cl1_addr = 0
    seq = 1
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl1_addr, seq, num_non_ows, num_ows)

    cl2_addr = cl1_addr + CACHELINE_BYTES
    seq = seq + 100
    num_non_ows = 4
    num_ows = dict()
    op_list += gen_stores(cl2_addr, seq, num_non_ows, num_ows)

    cl3_addr = cl2_addr + CACHELINE_BYTES

    cl4_addr = cl3_addr + CACHELINE_BYTES
    seq = seq + 100
    num_non_ows = 3
    num_ows = dict()
    op_list += gen_stores(cl4_addr, seq, num_non_ows, num_ows)

    seq = 10000
    fence = Fence(seq)
    op_list.append(fence)

    seq = 20000
    num_non_ows = 3
    num_ows = dict()
    op_list += gen_stores(cl1_addr, seq, num_non_ows, num_ows)

    seq = seq + 100
    num_non_ows = 5
    num_ows = dict()
    op_list += gen_stores(cl3_addr, seq, num_non_ows, num_ows)

    seq = seq + 100
    num_non_ows = 2
    num_ows = dict()
    op_list += gen_stores(cl4_addr, seq, num_non_ows, num_ows)

    seq = 30000
    fence = Fence(seq)
    op_list.append(fence)

    num_cps = gen_num_crash_plans(op_list)
    if num_cps == 37696:
        global_logger.info("test_2_1_1_case_1: %s" % (get_passed_str()))
    else:
        global_logger.info("test_2_1_1_case_1: %s" % (get_failed_str()))


if __name__ == "__main__":
    init_log()
    test_1_0_0_case_1()
    test_1_0_0_case_2()
    test_1_0_0_case_3()
    test_1_0_0_case_4()
    test_1_0_0_case_5()

    test_1_1_0_case_1()

    test_1_0_1_case_1()

    test_1_1_1_case_1()

    test_2_1_1_case_1()
