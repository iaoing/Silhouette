import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.vm_comm.heartbeat_guest import stop_heartbeat_service
import scripts.vm_comm.memcached_wrapper as mc_wrapper
import scripts.utils.logger as log

def signal_handler(signum, frame):
    msg = f"handle signale {signum} {frame} on {mc_wrapper.glo_vm_id}"
    log.global_logger.debug(msg)
    if mc_wrapper.glo_mc_pool_client != None:
        stop_heartbeat_service()
        mc_wrapper.glo_mc_pool_client.close()

    log.flush_all()
    sys.exit(1)
