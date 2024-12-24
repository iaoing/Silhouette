import sys
import logging, logging.handlers
import time
import pytz
import socketserver
import threading
import selectors
import socket
import select
import pickle
import struct
from datetime import datetime

global_logger = logging.getLogger("global_logger")
time_logger = logging.getLogger("time_logger")
debug = False
log_server = None

def posix2est(timestamp):
    """Seconds since the epoch -> local time as an aware datetime object."""
    timezone_est = pytz.timezone('US/Eastern')
    dt = datetime.fromtimestamp(timestamp, timezone_est)
    return dt

class TZConvertFormatter(logging.Formatter):
    def converter(self, timestamp):
        return posix2est(timestamp)

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            t = dt.strftime(self.default_time_format)
            s = self.default_msec_format % (t, record.msecs)
        return s

def setup_global_logger(fname=None, file_lv=40,
                        stm=None, stm_lv=50,
                        file_mode='a',
                        time_fname=None, time_file_mode='a',
                        host=None, port=None):
    global global_logger, time_logger, debug

    global_logger.setLevel(min(file_lv, stm_lv))

    if min(file_lv, stm_lv) <= 10:
        debug = True

    # formatter = logging.Formatter(fmt='%(levelname)s: (%(module)s:%(lineno)d,%(asctime)s.%(msecs)03d) - %(message)s', datefmt='%Y%m%d-%H:%M:%S')
    formatter = TZConvertFormatter(fmt='%(levelname)s: (%(module)s:%(lineno)d,%(asctime)s.%(msecs)03d) - %(message)s', datefmt='%Y%m%d-%H:%M:%S')

    if fname:
        file_handler = logging.FileHandler(fname, mode=file_mode)
        file_handler.setLevel(file_lv)
        file_handler.setFormatter(formatter)
        global_logger.addHandler(file_handler)

    if stm:
        stream_handler = logging.StreamHandler(stm)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(stm_lv)
        global_logger.addHandler(stream_handler)

    time_logger.setLevel(logging.INFO)
    if time_fname:
        file_handler = logging.FileHandler(time_fname, mode=time_file_mode)
        file_handler.setFormatter(formatter)
        time_logger.addHandler(file_handler)
    elif fname:
        file_handler = logging.FileHandler(fname, mode=file_mode)
        file_handler.setFormatter(formatter)
        time_logger.addHandler(file_handler)
    else:
        print("No logging file specified, timing information will not be logged.")

    if host and port:
        socketHandler = logging.handlers.SocketHandler(host, port)
        socketHandler.setLevel(logging.INFO)
        # does not need to set the format
        time_logger.addHandler(socketHandler)

def set_global_logger_level(file_lv=None, stm_lv=None):
    global global_logger

    lv = global_logger.level
    if file_lv:
        lv = min(lv, file_lv)
    if stm_lv:
        lv = min(lv, stm_lv)
    global_logger.setLevel(lv)

    for handler in global_logger.handlers:
        if file_lv and isinstance(handler, logging.FileHandler):
            handler.setLevel(file_lv)
        if stm_lv and isinstance(handler, logging.StreamHandler):
            handler.setLevel(stm_lv)

def flush_all():
    global global_logger, time_logger

    for handler in global_logger.handlers:
        handler.flush()
    for handler in time_logger.handlers:
        handler.flush()

class LogRecordSelectorBasedStreamHandler:
    def __init__(self, host, port, fpath, mode='a'):
        self.log_fpath = fpath
        self.time_receiver_logger = logging.getLogger("time_receiver_logger")
        self._setup_receive_logger(mode)

        self.host = host
        self.port = port
        self.selector = selectors.DefaultSelector()
        self.stop_event = threading.Event()
        self._setup_server()

    def _setup_receive_logger(self, mode):
        # the args is the remote port
        formatter = TZConvertFormatter(fmt='%(levelname)s: (%(module)s:%(lineno)d,%(asctime)s.%(msecs)03d) - %(message)s', datefmt='%Y%m%d-%H:%M:%S')
        file_handler = logging.FileHandler(self.log_fpath, mode)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        self.time_receiver_logger.addHandler(file_handler)
        self.time_receiver_logger.setLevel(logging.INFO)

    def _setup_server(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(65535)  # Queue up to 100 connections
        self.sock.setblocking(False)
        self.selector.register(self.sock, selectors.EVENT_READ, data=None)
        # print(f'Listening on {self.host}:{self.port}')

    def _handle_events(self, key, mask):
        if key.data is None:
            self._accept_connection(key.fileobj)
        else:
            self._receive_data(key.fileobj)

    def _accept_connection(self, sock):
        conn, addr = sock.accept()
        # print(f'Connection from {addr}')
        conn.setblocking(False)
        self.selector.register(conn, selectors.EVENT_READ, data=b'')

    def _receive_data(self, sock):
        data = sock.recv(4096)
        if len(data) < 4:
            return
        if data:
            try:
                self._process_data(data, sock.getpeername()[0], sock.getpeername()[1])
            except pickle.PickleError as e:
                print(f"LogRecordSelectorBasedStreamHandler PickleError: {e}")
            except Exception as e:
                print(f"LogRecordSelectorBasedStreamHandler Exception: {e}")
        else:
            self._close_connection(sock)

    def _process_data(self, data, remote_host, remote_port):
        length_prefix = data[:4]
        length = struct.unpack('>L', length_prefix)[0]
        log_data = data[4:4+length]
        log_record = pickle.loads(log_data)
        log_record['module'] = f'{remote_host}:{remote_port}:' + log_record['module']
        # print(log_record)
        record = logging.makeLogRecord(log_record)
        self.time_receiver_logger.handle(record)

    def _close_connection(self, sock):
        # print(f'Closing connection to {sock.getpeername()}')
        self.selector.unregister(sock)
        sock.close()

    def _serve_forever(self):
        try:
            while not self.stop_event.is_set():
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    self._handle_events(key, mask)
        except KeyboardInterrupt:
            print("Logging server is shutting down...")
        finally:
            self.selector.close()

    def serve_in_background(self):
        thd = threading.Thread(target=self._serve_forever)
        thd.daemon = True
        thd.start()

    def stop_background_server(self):
        self.stop_event.set()
        self.selector.close()
        self.sock.close()
        print("Logging Server stopped.")
