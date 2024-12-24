import os, sys
import socket

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger

FIRST_PORT_NUM = 8000
LAST_PORT_NUM = 65535

glo_start_port = FIRST_PORT_NUM

def port_in_using(port) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', port))
        return False
    except socket.error:
        return True
    finally:
        s.close()

def find_first_available_port():
    global glo_start_port
    start_port = glo_start_port
    for port in range(start_port, LAST_PORT_NUM + 1):
        if port_in_using(port):
            continue
        else:
            glo_start_port = port + 1
            return port
    global_logger.error("Could not find an available port.")
    return -1
