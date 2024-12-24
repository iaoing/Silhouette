import os
import sys
import time
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

import scripts.utils.logger as log
from scripts.utils.utils import generate_random_string
from scripts.fs_conf.base.env_phoney import EnvPhoney

env = EnvPhoney()
log.setup_global_logger(fname='xx.log', file_lv=40, stm=sys.stderr, stm_lv=40, host=env.TIME_LOG_SERVER_IP_ADDRESS_GUEST(), port=env.TIME_LOG_SERVER_PORT())

for i in range(0, 4096, 16):
    msg = generate_random_string(i)

    t1 = time.perf_counter()
    log.time_logger.info(msg)
    t2 = time.perf_counter()

    print(f"send {i} bytes msg: {t2-t1:.9f}")
