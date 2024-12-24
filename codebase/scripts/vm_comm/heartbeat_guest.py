import os
import sys
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache.exceptions import MemcacheUnexpectedCloseError, MemcacheUnknownError, MemcacheServerError
import time
import threading

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.const_var import HEARTBEAT_INTERVAL
import scripts.vm_comm.memcached_wrapper as mc_wrapper
import scripts.utils.logger as log

glo_stop_event = None
glo_heartbeat_thread = None

def send_heartbeat(memcached_client : CMPooledClient, key, stop_event):
    beat = 5 # in seconds
    while not stop_event.is_set():
        try:
            beat = memcached_client.incr(key, HEARTBEAT_INTERVAL)
        except MemcacheServerError as e:
            # continue to increment
            memcached_client.close()
            mc_wrapper.try_custom_connect()
            msg = f'{e}'
            log.global_logger.debug(msg)
        except MemcacheUnknownError as e:
            # continue to increment
            memcached_client.close()
            mc_wrapper.try_custom_connect()
            msg = f'{e}'
            log.global_logger.debug(msg)
        except Exception as e:
            memcached_client.close()
            mc_wrapper.try_custom_connect()
            msg = f'Failed to set {key} {beat} to memcached: {e}'
            log.global_logger.error(msg)
        finally:
            log.flush_all()

        # ignore exceptions, try the best to send heartbeat

        time.sleep(HEARTBEAT_INTERVAL)
        beat += HEARTBEAT_INTERVAL

    memcached_client.close()
    print("Heartbeat service stopped.")

def start_heartbeat_service(memcached_client : CMPooledClient, key):
    global glo_stop_event, glo_heartbeat_thread
    glo_stop_event = threading.Event()

    glo_heartbeat_thread = threading.Thread(target=send_heartbeat, args=(memcached_client, key, glo_stop_event))
    # glo_heartbeat_thread.setDaemon(True)
    glo_heartbeat_thread.start()

def stop_heartbeat_service():
    global glo_stop_event, glo_heartbeat_thread
    if glo_heartbeat_thread != None and glo_stop_event != None:
        glo_stop_event.set()
        glo_heartbeat_thread.join()
