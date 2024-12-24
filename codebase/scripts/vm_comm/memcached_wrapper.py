import os
import sys
from distutils.util import strtobool
import traceback
import socket
import time
import pymemcache.exceptions as pymc_exception
from pymemcache.client.base import _readline
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde
from pymemcache import MemcacheUnexpectedCloseError
from pymemcache.exceptions import MemcacheIllegalInputError

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.exceptions import GuestExceptionForDebug, GuestExceptionToRestartVM, MemcachedOPFailed
import scripts.utils.logger as log

MC_CONNECT_TIMEOUT = 5
MC_CMD_TIMEOUT = 5
MC_CMD_RETRY_TIMES = 5

glo_vm_id = None
glo_mc_server = None
glo_mc_port = None
glo_mc_pool_client : CMPooledClient = None

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.both.memcached_wrapper.{func.__name__}:{time.perf_counter() - start_time}")
        return result
    return wrapper

def setup_memcached_client(host, port, vm_id=None):
    global glo_vm_id, glo_mc_pool_client, glo_mc_server, glo_mc_port
    glo_vm_id = vm_id
    glo_mc_server = host
    glo_mc_port = port

    msg = f"setup memcached client: {host} {port} from {vm_id}"
    log.global_logger.debug(msg)

    glo_mc_pool_client = CMClient((host, port), serde=CMSerde.compressed_serde, connect_timeout=MC_CONNECT_TIMEOUT, timeout=MC_CMD_TIMEOUT, no_delay=True)

    return glo_mc_pool_client

def setup_memcached_pooled_client(host, port, vm_id=None):
    global glo_vm_id, glo_mc_pool_client, glo_mc_server, glo_mc_port
    glo_vm_id = vm_id
    glo_mc_server = host
    glo_mc_port = port

    msg = f"setup pooled memcached client: {host} {port} from {vm_id}"
    log.global_logger.debug(msg)

    glo_mc_pool_client = CMPooledClient((host, port), serde=CMSerde.compressed_serde, connect_timeout=MC_CONNECT_TIMEOUT, timeout=MC_CMD_TIMEOUT, no_delay=True)

    return glo_mc_pool_client

@timeit
def try_custom_connect():
    global glo_mc_server, glo_mc_port
    # Create a socket object
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to the server
        sock.settimeout(MC_CONNECT_TIMEOUT)
        sock.connect((glo_mc_server, int(glo_mc_port)))
        msg = f"try_custom_connect: connected to {glo_mc_server}:{glo_mc_port}"
        log.global_logger.debug(msg)

        # Close the socket
        sock.close()
        msg = f"try_custom_connect: closed"
        log.global_logger.debug(msg)

    except Exception as e:
        msg = f"try_custom_connect: exception {e}"
        log.global_logger.error(msg)
    finally:
        log.flush_all()

def _gen_mc_set_cmd_line(mc_client : CMPooledClient, cmd_name, key, value):
    key = mc_client.check_key(key)
    data, data_flags = mc_client.serde.serialize(key, value)
    expire_bytes = str(0).encode(mc_client.encoding)
    extra = b" noreply"

    if not isinstance(data, bytes):
        try:
            data = str(data).encode(mc_client.encoding)
        except UnicodeEncodeError as e:
            raise MemcacheIllegalInputError(
                "Data values must be binary-safe: %s" % e
            )
        finally:
            log.flush_all()

    cmds = []
    cmds.append(
        cmd_name
        + b" "
        + key
        + b" "
        + str(data_flags).encode(mc_client.encoding)
        + b" "
        + expire_bytes
        + b" "
        + str(len(data)).encode(mc_client.encoding)
        + extra
        + b"\r\n"
        + data
        + b"\r\n"
    )
    return cmds

@timeit
def custom_raw_set(mc_client : CMPooledClient, key, value):
    # only support noreply
    global glo_mc_server, glo_mc_port
    # Create a socket object
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to the server
        sock.settimeout(MC_CONNECT_TIMEOUT)
        sock.connect((glo_mc_server, int(glo_mc_port)))

        cmds = _gen_mc_set_cmd_line(mc_client, b'set', key, value)

        sock.sendall(b"".join(cmds))

        # Close the socket
        sock.close()

        return True

    except Exception as e:
        msg = f"custom_raw_set: exception {e}"
        log.global_logger.error(msg)
        raise
    finally:
        log.flush_all()

def mc_set_wrapper(mc_client : CMPooledClient, key, value, noreply=True):
    try:
        retry_times = MC_CMD_RETRY_TIMES
        while retry_times > 0:
            if retry_times != MC_CMD_RETRY_TIMES:
                mc_client.close()

            retry_times -= 1
            try:
                # use pymemcached and the custom raw set in interleaving
                if (MC_CMD_RETRY_TIMES - retry_times) % 2:
                    if not mc_client.set(key, value, noreply=noreply):
                        mc_client.close()
                        # try_custom_connect()
                    else:
                        # this function returns at here
                        return True
                else:
                    return custom_raw_set(mc_client, key, value)

            except Exception as e:
                msg = f"mc set exception: {e} at the {MC_CMD_RETRY_TIMES-retry_times}-th try"
                log.global_logger.error(msg)
                # close the connection and try again
                # mc_client.close()
                # try a custom connection
                # try_custom_connect()
            finally:
                log.flush_all()

        # if failed in {MC_CMD_RETRY_TIMES} times, try the raw set
        # retry_times = MC_CMD_RETRY_TIMES
        # while retry_times > 0:
        #     retry_times -= 1
        #     try:
        #         return custom_raw_set(mc_client, key, value)
        #     except Exception as e:
        #         msg = f"mc set custom_raw_set exception: {e} at the {MC_CMD_RETRY_TIMES-retry_times}-th try"
        #         log.global_logger.error(msg)

        msg = f"{traceback.format_exc()}\nmc set failed after trying {MC_CMD_RETRY_TIMES} times"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except MemcachedOPFailed as e:
        raise
    except MemcacheUnexpectedCloseError as e:
        msg = f"{traceback.format_exc()}\nmc set exception: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    except TimeoutError as e:
        msg = f"{traceback.format_exc()}\nmc set timeout: {e}"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except Exception as e:
        msg = f"{traceback.format_exc()}\nmc set unknown exceptions: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    finally:
        log.flush_all()

def mc_get_wrapper(mc_client : CMPooledClient, key, default_ret=None):
    try:
        retry_times = MC_CMD_RETRY_TIMES
        while retry_times > 0:
            retry_times -= 1
            try:
                return mc_client.get(key, default=default_ret)
            except Exception as e:
                msg = f"mc gets exception: {e} at the {MC_CMD_RETRY_TIMES-retry_times}-th try"
                log.global_logger.error(msg)
                # close the connection and try again
                mc_client.close()
                # try a custom connection
                try_custom_connect()

        msg = f"{traceback.format_exc()}\nmc gets failed after trying {MC_CMD_RETRY_TIMES} times"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except MemcachedOPFailed as e:
        raise
    except MemcacheUnexpectedCloseError as e:
        msg = f"{traceback.format_exc()}\nmc gets exception: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    except TimeoutError as e:
        msg = f"{traceback.format_exc()}\nmc gets timeout: {e}"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except Exception as e:
        msg = f"{traceback.format_exc()}\nmc gets unknown exceptions: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    finally:
        log.flush_all()

def mc_gets_wrapper(mc_client : CMPooledClient, key):
    try:
        retry_times = MC_CMD_RETRY_TIMES
        while retry_times > 0:
            retry_times -= 1
            try:
                value, cas_id = mc_client.gets(key)
                if cas_id == None:
                    mc_client.close()
                    try_custom_connect()
                else:
                    # this function returns at here
                    return value, cas_id
            except Exception as e:
                msg = f"mc gets exception: {e} at the {MC_CMD_RETRY_TIMES-retry_times}-th try"
                log.global_logger.error(msg)
                # close the connection and try again
                mc_client.close()
                # try a custom connection
                try_custom_connect()
            finally:
                log.flush_all()

        msg = f"{traceback.format_exc()}\nmc gets failed after trying {MC_CMD_RETRY_TIMES} times"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except MemcachedOPFailed as e:
        raise
    except MemcacheUnexpectedCloseError as e:
        msg = f"{traceback.format_exc()}\nmc gets exception: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    except TimeoutError as e:
        msg = f"{traceback.format_exc()}\nmc gets timeout: {e}"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except Exception as e:
        msg = f"{traceback.format_exc()}\nmc gets unknown exceptions: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    finally:
        log.flush_all()

def _gen_mc_incr_cmd_line(mc_client : CMPooledClient, key, value):
    key = mc_client.check_key(key)
    val = mc_client._create_client()._check_integer(value, "value")
    cmd = b"incr " + key + b" " + val
    cmd += b"\r\n"
    return cmd

@timeit
def custom_raw_incr(mc_client : CMPooledClient, key, num):
    global glo_mc_server, glo_mc_port
    # Create a socket object
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to the server
        sock.settimeout(MC_CONNECT_TIMEOUT)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((glo_mc_server, int(glo_mc_port)))

        cmd = _gen_mc_incr_cmd_line(mc_client, key, num)

        # send the incr command
        sock.sendall(cmd)

        # get the incremented number from memcached
        buf = b""
        line = None
        buf, line = _readline(sock, buf)

        # Close the socket
        sock.close()

        if line == b"NOT_FOUNT":
            return None
        elif line.startswith(b"ERROR"):
            msg = f"Unknown command error: {cmd}"
            log.global_logger.error(msg)
            raise pymc_exception.MemcacheError(msg)
        elif line.startswith(b"CLIENT_ERROR"):
            msg = f"Client error: {line}"
            log.global_logger.error(msg)
            raise pymc_exception.MemcacheClientError(msg)
        elif line.startswith(b"SERVER_ERROR"):
            msg = f"Server error: {line}"
            log.global_logger.error(msg)
            raise pymc_exception.MemcacheServerError(msg)
        else:
            return int(line)

    except Exception as e:
        msg = f"custom_raw_set: exception {e}"
        log.global_logger.error(msg)
        raise
    finally:
        log.flush_all()

def mc_add_wrapper(mc_client : CMPooledClient, key, value, noreply=False):
    ret = None
    try:
        retry_times = MC_CMD_RETRY_TIMES
        while retry_times > 0:
            if retry_times != MC_CMD_RETRY_TIMES:
                # the connection will be reestablishes when issusing cmd
                mc_client.close()

            retry_times -= 1
            try:
                # use pymemcached and the custom raw add in interleaving
                return mc_client.add(key, value, noreply=noreply)

            except Exception as e:
                msg = f"mc add exception: {e} at the {MC_CMD_RETRY_TIMES-retry_times}-th try"
                log.global_logger.error(msg)
                # close the connection and try again
                # mc_client.close()
                # try a custom connection
                # try_custom_connect()
            finally:
                log.flush_all()

        msg = f"{traceback.format_exc()}\nmc add failed after trying {MC_CMD_RETRY_TIMES} times"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except MemcachedOPFailed as e:
        raise
    except MemcacheUnexpectedCloseError as e:
        msg = f"{traceback.format_exc()}\nmc add exception: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    except TimeoutError as e:
        msg = f"{traceback.format_exc()}\nmc add timeout: {e}"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except Exception as e:
        msg = f"{traceback.format_exc()}\nmc add unknown exceptions: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    finally:
        log.flush_all()

def mc_incr_wrapper(mc_client : CMPooledClient, key, num):
    ret = None
    try:
        retry_times = MC_CMD_RETRY_TIMES
        while retry_times > 0:
            if retry_times != MC_CMD_RETRY_TIMES:
                # the connection will be reestablishes when issusing cmd
                mc_client.close()

            retry_times -= 1
            try:
                # use pymemcached and the custom raw set in interleaving
                ret = None
                if (MC_CMD_RETRY_TIMES - retry_times) % 2:
                    ret = mc_client.incr(key, num)
                else:
                    ret = custom_raw_incr(mc_client, key, num)

                if ret == None:
                    mc_client.close()
                    try_custom_connect()
                else:
                    return ret

            except Exception as e:
                msg = f"mc incr exception: {e} at the {MC_CMD_RETRY_TIMES-retry_times}-th try"
                log.global_logger.error(msg)
                # close the connection and try again
                # mc_client.close()
                # try a custom connection
                # try_custom_connect()
            finally:
                log.flush_all()

        msg = f"{traceback.format_exc()}\nmc incr failed after trying {MC_CMD_RETRY_TIMES} times"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except MemcachedOPFailed as e:
        raise
    except MemcacheUnexpectedCloseError as e:
        msg = f"{traceback.format_exc()}\nmc incr exception: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    except TimeoutError as e:
        msg = f"{traceback.format_exc()}\nmc incr timeout: {e}"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except Exception as e:
        msg = f"{traceback.format_exc()}\nmc incr unknown exceptions: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    finally:
        log.flush_all()

def mc_cas_wrapper(mc_client : CMPooledClient, key, value, cas_id):
    '''The value cannot be None'''
    ret = None
    try:
        retry_times = MC_CMD_RETRY_TIMES
        while retry_times > 0:
            retry_times -= 1
            try:
                ret = mc_client.cas(key, value, cas_id)
                if ret == None:
                    mc_client.close()
                    try_custom_connect()
                else:
                    return ret
            except Exception as e:
                msg = f"mc cas exception: {e} at the {MC_CMD_RETRY_TIMES-retry_times}-th try"
                log.global_logger.error(msg)
                # close the connection and try again
                mc_client.close()
                # try a custom connection
                try_custom_connect()
            finally:
                log.flush_all()

        msg = f"{traceback.format_exc()}\nmc cas failed after trying {MC_CMD_RETRY_TIMES} times"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except MemcachedOPFailed as e:
        raise
    except MemcacheUnexpectedCloseError as e:
        msg = f"{traceback.format_exc()}\nmc cas exception: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    except TimeoutError as e:
        msg = f"{traceback.format_exc()}\nmc cas timeout: {e}"
        log.global_logger.error(msg)
        raise MemcachedOPFailed(msg)
    except Exception as e:
        msg = f"{traceback.format_exc()}\nmc cas unknown exceptions: {e}"
        log.global_logger.error(msg)
        raise GuestExceptionForDebug(msg)
    finally:
        log.flush_all()
