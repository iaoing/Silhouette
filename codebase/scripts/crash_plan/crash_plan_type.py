from enum import Enum

class CrashPlanType(Enum):
    PrevOpOracle            = 'PrevOpOracle'
    PostOpOracle            = 'PostOpOracle'

    UnprotectedPersistSelf  = 'UnprotectedPersistSelf'
    UnprotectedPersistOther = 'UnprotectedPersistOther'

    MechPersistSelf         = 'MechPersistSelf'
    MechPersistOther        = 'MechPersistOther'

    UndojnlChkRecv          = 'UndojnlChkRecv'
    UndojnlUnsafe           = 'UndojnlUnsafe'

    RepChkRecv              = 'RepChkRecv'
    RepUnsafe               = 'RepUnsafe'

    LSWChkRecv              = 'LSWChkRecv'
    LSWUnsafe               = 'LSWUnsafe'

    CombPersist             = 'CombPersist'
    CombPersistSelf         = 'CombPersistSelf'
    CombPersistOther        = 'CombPersistOther'

    Dummy                   = 'Dummy'

    Unknown                 = 'Unknown'

    def dummy_crash_plan(self):
        return self.value == 'Dummy'

    def no_content_to_check(self):
        return self.value in ['CombPersist', 'CombPersistSelf', 'CombPersistOther', 'Dummy']

class CrashPlanSamplingType(Enum):
    SamplingNone   = 'SamplingNone'
    SamplingAtomic = 'SamplingAtomic'
