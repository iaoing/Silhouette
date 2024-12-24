import os
import sys
import traceback

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, GuestExceptionToRestoreSnapshot, GuestExceptionForValidation, MemcachedOPFailed
from scripts.vm_comm.heartbeat_guest import stop_heartbeat_service
from scripts.vm_mgr.guest_state import GuestState
import scripts.vm_comm.memcached_wrapper as mc_wrapper
import scripts.utils.logger as log

def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """ handle all uncaught exceptions """
    if issubclass(exc_type, GuestExceptionToRestartVM):
        if mc_wrapper.glo_mc_pool_client != None and mc_wrapper.glo_vm_id != None:
            key = f'{mc_wrapper.glo_vm_id}.state'
            value = GuestState.NEED_RESTART_VM
            mc_wrapper.glo_mc_pool_client.set(key, value)

    elif issubclass(exc_type, GuestExceptionToRestoreSnapshot):
        if mc_wrapper.glo_mc_pool_client != None and mc_wrapper.glo_vm_id != None:
            key = f'{mc_wrapper.glo_vm_id}.state'
            value = GuestState.NEED_RESTORE_SNAPSHOT
            mc_wrapper.glo_mc_pool_client.set(key, value)

    elif issubclass(exc_type, GuestExceptionForDebug):
        if mc_wrapper.glo_mc_pool_client != None and mc_wrapper.glo_vm_id != None:
            key = f'{mc_wrapper.glo_vm_id}.state'
            value = GuestState.NEED_DEBUG
            mc_wrapper.glo_mc_pool_client.set(key, value)

    elif issubclass(exc_type, GuestExceptionForValidation):
        if mc_wrapper.glo_mc_pool_client != None and mc_wrapper.glo_vm_id != None:
            key = f'{mc_wrapper.glo_vm_id}.state'
            value = GuestState.VALIDATION_FAILED
            mc_wrapper.glo_mc_pool_client.set(key, value)

    elif issubclass(exc_type, MemcachedOPFailed):
        if mc_wrapper.glo_mc_pool_client != None and mc_wrapper.glo_vm_id != None:
            key = f'{mc_wrapper.glo_vm_id}.state'
            value = GuestState.NEED_RESTART_VM
            mc_wrapper.glo_mc_pool_client.set(key, value)

    else:
        if mc_wrapper.glo_mc_pool_client != None and mc_wrapper.glo_vm_id != None:
            key = f'{mc_wrapper.glo_vm_id}.state'
            value = GuestState.UNKNOWN
            mc_wrapper.glo_mc_pool_client.set(key, value)
        else:
            # do nothing
            pass

    if mc_wrapper.glo_mc_pool_client != None:
        stop_heartbeat_service()
        mc_wrapper.glo_mc_pool_client.close()

    print ("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    log.global_logger.critical("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    log.flush_all()
    sys.exit(1)
