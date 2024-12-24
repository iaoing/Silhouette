from enum import Enum

class GuestState(Enum):
    # This state should never be used.
    NOT_STARTED           = 1
    # The host will set this state to indicate the guest-side script is started via SSH.
    STARTED               = 2
    # The guest set this state. In the `initing` state, the host does not check heartbeat.
    INITING               = 3
    # The guest set this state, indicating the init of the guest class is done.
    INITED                = 4
    # The guest set this state, indicating the guest is starting to running test cases.
    RUNNING               = 5
    # The guest set this state, indicating all test cases are done.
    COMPLETE              = 6
    # The guest set this state, indicating the host need to restore the snapshot of this VM.
    NEED_RESTORE_SNAPSHOT = 7
    # The guest set this state, indicating the host need to restart VM.
    NEED_RESTART_VM       = 8
    # The guest validation found errors
    VALIDATION_FAILED     = 9
    # The guest set this state, indicating some unexpected errors occur. In this state, the host will not checking and manage this VM (e.g., restart) so that the user can SSH to this VM and check details.
    NEED_DEBUG            = 99
    # Unknown
    UNKNOWN               = 255
