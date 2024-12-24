from aenum import Enum

class CommMsgType(Enum):
    """Types of trace entries."""
    _init_ = 'value string'

    # client to server msg header
    C2S_REQ_ACK_TYPE             = 1, 'C2S_REQ_ACK_TYPE'
    C2S_REQ_TEST_CASE_TYPE       = 2, 'C2S_REQ_TEST_CASE_TYPE'
    C2S_REQ_TRACE_SEQ_CHECK_TYPE = 3, 'C2S_REQ_TRACE_SEQ_CHECK_TYPE'

    C2S_TRANSF_RAW_TRACE_TYPE    = 4, 'C2S_TRANSF_RAW_TRACE_TYPE'
    C2S_TRANSF_CRASH_PLAN_TYPE   = 5, 'C2S_TRANSF_CRASH_PLAN_TYPE'
    C2S_TRANSF_DISK_CONTENT_TYPE = 6, 'C2S_TRANSF_DISK_CONTENT_TYPE'
    C2S_TRANSF_SYS_LOG_TYPE      = 7, 'C2S_TRANSF_SYS_LOG_TYPE'
    C2S_TRANSF_TIMER_MSG_TYPE    = 8, 'C2S_TRANSF_TIMER_MSG_TYPE'
    C2S_TRANSF_DBG_MSG_TYPE      = 9, 'C2S_TRANSF_DBG_MSG_TYPE'
    C2S_TRANSF_RUN_LOG_TYPE      = 10, 'C2S_TRANSF_RUN_LOG_TYPE'

    # server to client msg header
    S2C_REP_ACK_TYPE             = 11, 'S2C_REP_ACK_TYPE'
    S2C_REP_TEST_CASE_TYPE       = 12, 'S2C_REP_TEST_CASE_TYPE'
    S2C_REP_TRACE_SEQ_CHECK_TYPE = 13, 'S2C_REP_TRACE_SEQ_CHECK_TYPE'

    # CTL
    CONNECTION_CLOSED            = 14, 'CONNECTION_CLOSED'
    GOOD_MSG                     = 15, 'GOOD_MSG'
    ERROR_WHEN_SENDING           = 16, 'ERROR_WHEN_SENDING'
    ERROR_WHEN_RECEIVING         = 16, 'ERROR_WHEN_RECEIVING'

    # ticktock
    TICKTOCK                     = 17, 'TICKTOCK'

    def __str__(self):
        return self.string

    @classmethod
    def _missing_value_(cls, value):
        for member in cls:
            if member.string == value:
                return member
        print("no ", value, " in CommMsgType")
        exit(1)
