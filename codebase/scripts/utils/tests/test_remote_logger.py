import os
import sys
import logging
import time
import pytz
import socketserver
import pickle
import struct
import threading
from datetime import datetime

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

import scripts.utils.logger as log

HOST = 'localhost'
PORT = 15531

def guest_thd(thd_num):
    for i in range(100):
        time.sleep(1)
        log.time_logger.info(f"#{thd_num}: {i}-th log")

def host_thd():
    tcpserver = log.LogRecordSocketReceiver(host=HOST, port=PORT)
    tcpserver.serve_in_background()

def main():
    log.setup_global_logger('xx.log', 10, sys.stdout, 30, host=HOST, port=PORT, time_fname='log.time.guest')

    host_server = log.LogRecordSelectorBasedStreamHandler(host=HOST, port=PORT, fpath='./log.time.remote')
    host_server.serve_in_background()

    guest_thread1 = threading.Thread(target=guest_thd, args=[1])
    guest_thread1.daemon = True  # This ensures the server thread will exit when the main thread does
    guest_thread1.start()

    guest_thread2 = threading.Thread(target=guest_thd, args=[2])
    guest_thread2.daemon = True  # This ensures the server thread will exit when the main thread does
    guest_thread2.start()

    time.sleep(10)
    host_server.stop_background_server()

    exit(0)

if __name__ == "__main__":
    main()
