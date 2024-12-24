class GuestExceptionToRestoreSnapshot(Exception):
    def __str__(self):
        return f"{self.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}"

class GuestExceptionToRestartVM(Exception):
    def __str__(self):
        return f"{self.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}"

class GuestExceptionForDebug(Exception):
    def __str__(self):
        return f"{self.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}"

class GuestExceptionForValidation(Exception):
    def __str__(self):
        return f"{self.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}"

class MemcachedOPFailed(Exception):
    '''
    Sometime, the memcached operation might failed due to timeout or network unreachable.
    Expect a VM restart under this exception.
    '''
    def __str__(self):
        return f"{self.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}"
