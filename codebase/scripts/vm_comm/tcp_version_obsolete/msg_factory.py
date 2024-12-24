import os
import sys
import struct
import pickle

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.vm_comm.msg_type import CommMsgType
from scripts.utils.logger import global_logger

MSG_MAGIC_HEADER = b'abcd'

class CommMessage():
    def __init__(self):
        self.type : CommMsgType = None
        self.obj = None

    def __repr(self):
        return self.type.__str__()

    def __str__(self):
        return self.type.__str__()

    def is_type(self, tp) -> bool:
        return self.type == tp

def pack_comm_msg(msg) -> bytes:
    return pickle.dumps(msg)

def unpack_comm_msg(data) -> CommMessage:
    return pickle.loads(data)

def build_c2s_ack_msg() -> CommMessage:
    msg = CommMessage()
    msg.type = CommMsgType.C2S_REQ_ACK_HEADER
    return msg

def build_s2c_ack_msg() -> CommMessage:
    msg = CommMessage()
    msg.type = CommMsgType.S2C_REP_ACK_HEADER
    return msg

def build_c2s_test_case_msg() -> CommMessage:
    msg = CommMessage()
    msg.type = CommMsgType.C2S_REQ_TEST_CASE_HEADER
    return msg

def build_s2c_test_case_msg(test_case_num : int) -> CommMessage:
    msg = CommMessage()
    msg.type = CommMsgType.S2C_REP_TEST_CASE_HEADER
    msg.obj = test_case_num
    return msg

def build_c2s_trace_seq_check_msg(trace_seq : list) -> CommMessage:
    # trace_seq: a list of seq id (int)
    msg = CommMessage()
    msg.type = CommMsgType.C2S_REQ_TRACE_SEQ_CHECK_HEADER
    msg.obj = trace_seq
    return msg

def build_s2c_trace_seq_check_msg(check_rst : bool) -> CommMessage:
    msg = CommMessage()
    msg.type = CommMsgType.S2C_REP_TRACE_SEQ_CHECK_HEADER
    msg.obj = check_rst
    return msg

class TranferFileEntry():
    def __init__(self, file_path, file_content):
        self.file_name = None
        self.file_content = None

        self.file_name = os.path.basename(file_path)
        self.file_content = file_content
        if self.file_content == None:
            with open(file_path, 'rb') as fd:
                self.file_content = fd.read()

def build_c2s_raw_trace_msg(file_path, file_content=None):
    msg = CommMessage()
    msg.type = CommMsgType.C2S_TRANSF_RAW_TRACE_HEADER
    msg.obj = TranferFileEntry(file_path, file_content)
    return msg

def build_c2s_crash_plan_msg(crash_plan) -> CommMessage:
    msg = CommMessage()
    msg.type = CommMsgType.C2S_TRANSF_CRASH_PLAN_HEADER
    msg.obj = crash_plan
    return msg

def build_c2s_disk_content_msg(file_path, file_content=None):
    msg = CommMessage()
    msg.type = CommMsgType.C2S_TRANSF_DISK_CONTENT_HEADER
    msg.obj = TranferFileEntry(file_path, file_content)
    return msg

def build_c2s_disk_content_msg(syslog : str):
    msg = CommMessage()
    msg.type = CommMsgType.C2S_TRANSF_SYS_LOG_HEADER
    msg.obj = syslog
    return msg

def build_c2s_timer_msg(timer_obj):
    msg = CommMessage()
    msg.type = CommMsgType.C2S_TRANSF_TIMER_type
    msg.obj = timer_obj
    return msg

def build_c2s_disk_content_msg(dbg_msg : str):
    msg = CommMessage()
    msg.type = CommMsgType.C2S_TRANSF_DBG_type
    msg.obj = dbg_msg
    return msg

def build_c2s_run_log_msg(file_path, file_content=None):
    msg = CommMessage()
    msg.type = CommMsgType.C2S_TRANSF_RUN_LOG_HEADER
    msg.obj = TranferFileEntry(file_path, file_content)
    return msg


def build_ticktock_msg():
    msg = CommMessage()
    msg.type = CommMsgType.TICKTOCK
    return msg
