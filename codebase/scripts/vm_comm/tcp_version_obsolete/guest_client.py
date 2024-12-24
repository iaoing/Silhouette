import socket
import os
import sys
import socket
import struct
import threading
import time

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger, setup_global_logger, logging
from scripts.vm_comm.msg_type import CommMsgType
import scripts.vm_comm.msg_factory as msg_factory

class GuestClient():
    """docstring for GuestClient."""
    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port
        self.connection : socket = None
        self.connection_alive = False
        self.__init_connection()

        # The connection is a critical section
        self.lock = threading.Lock()

    def __init_connection(self):
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.connect((self.server_host, self.server_port))
            self.connection.setblocking(True)
            self.connection.settimeout(5)
        except Exception as e:
            err_msg = f"{repr(e)} when connecting to {self.server_host}:{self.server_port}"
            global_logger.error(err_msg)
            return

        self.connection_alive = True
        dbg_msg = f"Connected to {self.server_host}:{self.server_port}, {self.connection}"
        global_logger.debug(dbg_msg)

    def ticktock_thread(self):
        msg = msg_factory.build_ticktock_msg()

        while True:
            # ticktock in 5 seconds
            time.sleep(5)

            try:
                self.send_msg(msg)
            except Exception as e:
                err_msg = f"{repr(e)} when ticktocking {self.server_host}:{self.server_port} {self.connection}"
                global_logger.error(err_msg)
                self.connection_alive = False
                return

    def start_bg_ticktock(self):
        self.ticktock_thread = threading.Thread(target=self.ticktock_thread)
        self.ticktock_thread.start()

    def server_alive(self) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(True)
            sock.settimeout(5)
            sock.connect((self.server_host, self.server_port))
            sock.close()
            return True

        except Exception as e:
            err_msg = f"{repr(e)} when checking server alive"
            global_logger.error(err_msg)
            return False

    def send_msg(self, msg : msg_factory.CommMessage):
        msg_buf : bytes = msg_factory.pack_comm_msg(msg)
        msg_len = len(msg_buf)
        msg_header = struct.pack('!i4s', msg_len, msg_factory.MSG_MAGIC_HEADER)

        try:
            self.lock.acquire()
            self.connection.sendall(msg_header)
            self.connection.sendall(msg_buf)

            dbg_msg = f"sending {msg_len} bytes {msg} to {self.connection}"
            global_logger.debug(dbg_msg)

        except Exception as e:
            raise e

        finally:
            self.lock.release()

    def recv_msg(self) -> bytes:
        msg_data = b''
        try:
            self.lock.acquire()
            self.connection.settimeout(5)
            msg_buf = self.connection.recv(8)

            if not msg_buf:
                dbg_msg = f"connection closed {self.server_host}:{self.server_port} {self.connection}"
                global_logger.debug(dbg_msg)
                self.close()
                return False

            if len(msg_buf) < 8:
                dbg_msg = f"Received fewer {len(msg_buf)} than 8 bytes {self.server_host}:{self.server_port} {self.connection}"
                global_logger.debug(dbg_msg)
                self.close()
                return False

            (msg_len, magic_num, ) = struct.unpack('!i4s', msg_buf)
            if magic_num != msg_factory.MSG_MAGIC_HEADER:
                err_msg = f"invalid magic number {magic_num} received from {self.server_host}:{self.server_port} {self.connection}"
                global_logger.error(err_msg)
                return False

            while msg_len > 0:
                if msg_len > 0:
                    msg_buf = self.client_connection.recv(1024, socket.MSG_WAITALL)
                    msg_len -= 1024
                else:
                    msg_buf = self.client_connection.recv(msg_len, socket.MSG_WAITALL)
                    msg_len -= msg_len

                if not msg_buf:
                    dbg_msg = f"connection closed {self.server_host}:{self.server_port} {self.connection}"
                    global_logger.debug(dbg_msg)
                    self.close()
                    return False

                msg_data += msg_buf

            return msg_data

        except Exception as e:
            err_msg = f"{repr(e)} when receiving from {self.server_host}:{self.server_port} {self.connection}"
            global_logger.error(err_msg)
            return False

        finally:
            self.lock.release()

    def handle_ack_msg(self) -> CommMsgType:
        # 1. send req ack msg to server
        msg : msg_factory.CommMessage = msg_factory.build_c2s_ack_msg()

        try:
            self.send_msg(msg)
        except Exception as e:
            err_msg = f"{repr(e)} when sending to {self.server_host}:{self.server_port} {self.connection}"
            global_logger.error(err_msg)
            return CommMsgType.ERROR_WHEN_SENDING

        # 2. receive ack msg from server
        msg_data = self.recv_msg()

        # 3. validate the received msg type
        msg : msg_factory.CommMessage = msg_factory.unpack_comm_msg(msg_data)
        if not msg.is_type(CommMsgType.S2C_REP_ACK_TYPE):
            err_msg = f"Invalid msg type {msg.type} received from {self.server_host}:{self.server_port} {self.connection}"
            global_logger.error(err_msg)
            return CommMsgType.ERROR_WHEN_RECEIVING

        dbg_msg = f"Received {msg.type} from {self.server_host}:{self.server_port} {self.connection}"
        global_logger.debug(dbg_msg)
        return CommMsgType.GOOD_MSG

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

