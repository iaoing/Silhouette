import os
import sys

from aenum import Enum

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

class TraceType(Enum):
    """Types of trace entries."""
    _init_ = 'value string'

    kStartFn        = 1,  'startFunc'
    kEndFn          = 2,  'endFunc'
    kStartBB        = 3,  'startBB'
    kEndBB          = 4,  'endBB'
    kLoad           = 5,  'load'
    kStore          = 6,  'store'
    kFence          = 7,  'fence'
    kXchg           = 8,  'xchg'
    kRMW            = 9,  'rmw'
    kMemset         = 10, 'memset'
    kMemTransLoad   = 11, 'memtransLoad'
    kMemTransStore  = 12, 'memtransStore'
    kAsmFlush       = 13, 'asmFlush'
    kAsmFence       = 14, 'asmFence'
    kAsmXchg        = 15, 'asmxchg'
    kAsmCAS         = 30, 'cas'
    kAsmMemsetNT    = 16, 'asmmemsetnt'
    kUKAsm          = 17, 'ukasm'
    kSelect         = 18, 'select'
    kStartCall      = 19, 'startCall'
    kEndCall        = 20, 'endCall'
    kUAccessLoad    = 21, 'uaccessLoad'
    kUAccessStore   = 22, 'uaccessStore'
    kUAccessLoadNT  = 23, 'uaccessNTLoad'
    kUAccessStoreNT = 24, 'uaccessNTStore'
    kDaxDevInfo     = 25, 'DaxDevInfo'
    kPMStPtr        = 26, 'PMStructPtr'
    kDramStPtr      = 27, 'DRAMStructPtr'
    kUkStPtr        = 28, 'UKStructPtr'
    kDbgStore       = 29, 'dbgStore'
    kCentFlush      = 31, 'centflush'
    kImpFence       = 32, 'impFence'

    def isStartCallTy(self):
        if self.value == TraceType.kStartCall.value:
            return True
        return False

    def isEndCallTy(self):
        if self.value == TraceType.kEndCall.value:
            return True
        return False

    def isLoadSeries(self):
        if self.value in [TraceType.kLoad.value, TraceType.kMemTransLoad.value, TraceType.kUAccessLoad.value, TraceType.kUAccessLoadNT.value]:
            return True
        return False

    def isStoreSeries(self):
        if self.value in [TraceType.kStore.value, TraceType.kUAccessStore.value, TraceType.kAsmMemsetNT.value, TraceType.kMemset.value, TraceType.kMemTransStore.value, TraceType.kUAccessStoreNT.value, TraceType.kAsmXchg.value, TraceType.kXchg.value, TraceType.kRMW.value, TraceType.kAsmCAS.value]:
            return True
        return False

    def isFlushTy(self):
        if self.value == TraceType.kAsmFlush.value:
            return True
        return False

    def isFenceTy(self):
        if self.value in [TraceType.kAsmFence.value, TraceType.kFence.value, TraceType.kImpFence.value]:
            return True
        return False

    def isImpFenceTy(self):
        if self.value == TraceType.kImpFence.value:
            return True
        return False

    def isStoreAndFlushTy(self):
        # non-temporary stores
        if self.value in [TraceType.kAsmMemsetNT.value, TraceType.kUAccessStoreNT.value]:
            return True
        return False

    def isPMRelatedTy(self):
        return self.isLoadSeries() or self.isStoreSeries() or \
                self.isFlushTy() or self.isFenceTy() or \
                self.isStoreAndFlushTy()

    def isDaxDevTy(self):
        return self.value == TraceType.kDaxDevInfo.value

    def isCASTy(self):
        return self.value == TraceType.kAsmCAS.value

    def isMemset(self):
        return self.value in [TraceType.kMemset.value, TraceType.kAsmMemsetNT.value]

    def isMemTransLoad(self):
        return self.value in [TraceType.kMemTransLoad.value, TraceType.kUAccessLoad.value, TraceType.kUAccessLoadNT.value]

    def isMemTransStore(self):
        return self.value in [TraceType.kMemTransStore.value, TraceType.kUAccessStore.value, TraceType.kUAccessStoreNT.value]

    def isStructInfoSeries(self):
        return self.value in [TraceType.kPMStPtr.value, TraceType.kDramStPtr.value, TraceType.kUkStPtr.value, TraceType.kDbgStore.value]

    def isCentflush(self):
        return self.value == TraceType.kCentFlush.value

    def __str__(self):
        return self.string

    @classmethod
    def _missing_value_(cls, name):
        for member in cls:
            if member.string == name:
                return member
        print("no ", name, " in Enum")
        exit(1)