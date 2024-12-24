import os
import sys
import time
import traceback

class GuestExceptionToRestartVM(Exception):
    pass

class GuestExceptionForDebug(Exception):
    pass

def handle_exception(exc_type, exc_value, exc_traceback):
    """ handle all uncaught exceptions """
    if issubclass(exc_type, GuestExceptionToRestartVM):
        print(f'got {GuestExceptionToRestartVM}')

    elif issubclass(exc_type, GuestExceptionForDebug):
        print(f'got {GuestExceptionForDebug}')

    else:
        print(f'got unknown exceptions {exc_type}')

    print ("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    sys.exit(1)

def e1():
    msg = f"from e1"
    raise GuestExceptionToRestartVM(msg)

if __name__ == "__main__":
    sys.excepthook = handle_exception
    e1()