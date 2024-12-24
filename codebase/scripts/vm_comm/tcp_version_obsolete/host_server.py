import os
import sys
import select
import socket
import threading
import queue
import struct
import traceback
from typing import Tuple

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger, setup_global_logger, logging
from scripts.vm_comm.msg_type import CommMsgType
import scripts.vm_comm.msg_factory as msg_factory

class HostServer():
    def __init__(self, host, port):
        self.server_host = host
        self.server_port = port
        self.server_socket = None

        self.client_connection = None
        self.client_addr = None

        self.__init_connection()

    def __init_connection(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.server_host, self.server_port))
            self.server_socket.setblocking(True)
            self.server_socket.settimeout(5)
            self.server_socket.listen()
        except Exception as e:
            err_msg = f"{repr(e)} when listening on {self.server_host}:{self.server_port}"
            global_logger.error(err_msg)
            return

        dbg_msg = f"Listening on {self.server_host}:{self.server_port}, {self.server_socket}"
        global_logger.debug(dbg_msg)

    def close_connection(self):
        if self.client_connection != None:
            self.client_connection.close()
            self.client_connection = None

    def wait_connect(self) -> bool:
        self.server_socket.setblocking(True)
        self.server_socket.settimeout(10)
        while True:
            try:
                self.client_connection, self.client_addr = self.server_socket.accept()
                dbg_msg = f"Accepted connection from {self.client_addr}, {self.client_connection}"
                global_logger.debug(dbg_msg)
                return True
            except socket.timeout:
                continue
            except socket.error as e:
                err_msg = f"{repr(e)} when accepting connection"
                global_logger.error(err_msg)
                return False

    def receive_msg(self) -> Tuple[CommMsgType, msg_factory.CommMessage]:
        msg_len = 0
        msg_data = b''
        self.client_connection.setblocking(True)
        self.client_connection.settimeout(10)

        # 1. receiving header
        while True:
            msg_len = 0
            try:
                msg_buf = self.client_connection.recv(8, socket.MSG_WAITALL)

                if not msg_buf:
                    warn_msg = f"connection closed {self.client_connection}"
                    global_logger.warn(warn_msg)
                    self.close()
                    return CommMsgType.CONNECTION_CLOSED, None

                if len(msg_buf) < 8:
                    warn_msg = f"Received fewer {len(msg_buf)} than 8 bytes {self.client_connection}"
                    global_logger.warn(warn_msg)
                    self.close()
                    return CommMsgType.ERROR_WHEN_RECEIVING, None

                (msg_len, magic_num) = struct.unpack('!i4s', msg_buf)
                if magic_num != msg_factory.MSG_MAGIC_HEADER:
                    warn_msg = f"invalid magic number {magic_num} received from {self.client_connection}"
                    global_logger.warn(warn_msg)
                    self.close()
                    return CommMsgType.ERROR_WHEN_RECEIVING, None

                break

            except socket.timeout:
                warn_msg = f"receiving timeout {self.client_connection}"
                global_logger.warn(warn_msg)
                self.close()
                return CommMsgType.CONNECTION_CLOSED, None

            except Exception as e:
                warn_msg = f"{repr(e)}, connection closed {self.client_connection}"
                global_logger.warn(warn_msg)
                self.close()
                return CommMsgType.CONNECTION_CLOSED, None

        dbg_msg = f"Received msg header with size {msg_len} from {self.client_connection}"
        global_logger.debug(dbg_msg)

        # 2. receive msg
        try:
            while msg_len > 0:
                if msg_len > 0:
                    msg_buf = self.client_connection.recv(1024, socket.MSG_WAITALL)
                    msg_len -= 1024
                else:
                    msg_buf = self.client_connection.recv(msg_len, socket.MSG_WAITALL)
                    msg_len -= msg_len

                if not msg_buf:
                    warn_msg = f"Connection closed {self.client_connection}"
                    global_logger.warn(warn_msg)
                    self.close()
                    return CommMsgType.CONNECTION_CLOSED, None

                msg_data += msg_buf

        except Exception as e:
            warn_msg = f"{repr(e)} when receiving from {self.client_connection}"
            global_logger.warn(warn_msg)
            return CommMsgType.ERROR_WHEN_RECEIVING, None

        msg = msg_factory.unpack_comm_msg(msg_data)
        dbg_msg = f"Received msg {msg} from {self.client_connection}"
        global_logger.debug(dbg_msg)
        return CommMsgType.GOOD_MSG, msg

    def send(self, msg : msg_factory.CommMessage) -> CommMsgType:
        msg_buf : bytes = msg_factory.pack_comm_msg(msg)
        msg_len = len(msg_buf)
        header = struct.pack('!i4s', msg_len, msg_factory.MSG_MAGIC_HEADER)

        try:
            self.client_connection.sendall(header)
            self.client_connection.sendall(msg_buf)
        except Exception as e:
            err_msg = f"{repr(e)} when sending to {self.client_connection}"
            global_logger.error(err_msg)
            return CommMsgType.ERROR_WHEN_SENDING

        return CommMsgType.GOOD_MSG

    def close(self):
        if self.client_connection != None:
            self.client_connection.close()
            self.client_connection = None
        if self.server_socket != None:
            self.server_socket.close()
            self.server_socket = None
