import os, sys
import psutil
import ctypes
import datetime
import stat
import shutil
import random
import string
import pytz
from struct import *

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger
from scripts.utils.const_var import CACHELINE_BYTES

TIMEZONE_EST = pytz.timezone('US/Eastern')

def isUserSpaceAddr(addr, is_x86_64 = True) -> bool:
    # https://linux-kernel-labs.github.io/refs/heads/master/lectures/address-space.html#linux-address-space
    # https://www.kernel.org/doc/html/latest/x86/x86_64/mm.html
    if is_x86_64:
        return addr < int('0x8000000000000000', 16)
    else:
        return addr < int('0xC0000000', 16)

def isKernelSpaceAddr(addr, is_x86_64 = True) -> bool:
    # https://linux-kernel-labs.github.io/refs/heads/master/lectures/address-space.html#linux-address-space
    # https://www.kernel.org/doc/html/latest/x86/x86_64/mm.html
    if is_x86_64:
        return addr >= int('0x8000000000000000', 16)
    else:
        return addr >= int('0xC0000000', 16)

def addrRangeToCachelineList(start_addr, end_addr) -> list:
    start_addr = alignToFloor(start_addr, CACHELINE_BYTES)
    end_addr = alignToFloor(end_addr, CACHELINE_BYTES)
    rst = []
    while start_addr <= end_addr:
        rst.append(start_addr)
        start_addr += CACHELINE_BYTES
    return rst

def inTheSameCacheLine(addr1, addr2):
    return (addr1 % CACHELINE_BYTES == addr2 % CACHELINE_BYTES)

def isAlignedBy(num, align):
    return (num % align == 0)

def alignToFloor(x : int, align : int) -> int:
    return x // align * align

def alignToCeil(x : int, align : int) -> int:
    ''' if aleady aligned, return the next aligned address '''
    return (1 + (x // align)) * align

def isOverlapping(x : list, y : list) -> bool:
    return x[0] <= y[1] and y[0] <= x[1]

def isContain(x : list, y : list) -> bool:
    """return true if x constains y"""
    return x[0] <= y[0] and x[1] >= y[1]

def intToU64Bytes(num : int):
    return pack('<Q', ctypes.c_uint64(num).value)

def intToU32Bytes(num : int):
    return pack('<I', ctypes.c_uint32(num).value)

def bytesToHexStr(buf):
    return ' '.join('{:02x}'.format(x) for x in buf)

def getMountPointFreeSpaceSizeMiB(path) -> float:
    available_space = psutil.disk_usage(path).free
    return available_space / 1024 / 1024

def getMountPointFreeSpaceSizeGiB(path) -> float:
    available_space = psutil.disk_usage(path).free
    return available_space / 1024 / 1024 / 1024

def envVarExist(env_name):
    return env_name in os.environ

def getEnvVar(env_name):
    # return None if does not exist
    return os.environ.get(env_name)

def fileExists(fname):
    return os.path.isfile(fname)

def diskExists(path):
    try:
        return stat.S_ISBLK(os.stat(path).st_mode)
    except:
        return False

def dirExists(dirname):
    return os.path.isdir(dirname)

def dirEmpty(dirname):
    if dirExists(dirname) and os.path.isdir(dirname):
        return not next(os.scandir(dirname), None)
    return False

def removeDir(dirname, force=False):
    if not force:
        try:
            os.rmdir(dirname)
        except OSError as e:
            err_msg = "error: os.rmdir(%s) failed: %s" % (dirname, e.strerror)
            global_logger.error(err_msg)
            return False
    else:
        try:
            shutil.rmtree(dirname)
        except shutil.Error as e:
            err_msg = "error: shutil.rmtree(%s) failed: %s" % (dirname, e.strerror)
            global_logger.error(err_msg)
            return False
    return True

def createFile(fname, size=0):
    try:
        fd = open(fname, 'wb')
        if size > 0:
            fd.truncate(size)
        fd.close()
    except OSError as e:
        err_msg = "error: open(%s) failed: %s" % (fname, e.strerror)
        global_logger.error(err_msg)
        return False
    return True

def mkdirDir(dirname, mode=0o777):
    try:
        os.mkdir(dirname, mode=mode)
    except OSError as e:
        err_msg = "error: os.mkdir(%s) failed: %s" % (dirname, e.strerror)
        global_logger.error(err_msg)
        return False
    return True

def mkdirDirs(dirname, mode=0o777, exist_ok=False):
    try:
        os.makedirs(dirname, mode=mode, exist_ok=exist_ok)
    except OSError as e:
        err_msg = "error: os.makedirs(%s) failed: %s" % (dirname, e.strerror)
        global_logger.error(err_msg)
        return False
    return True

def removeFile(fname):
    try:
        os.remove(fname)
    except OSError as e:
        err_msg = "error: os.remove(%s) failed: %s" % (fname, e.strerror)
        global_logger.error(err_msg)
        return False
    return True

def copyFile(f1, f2, keep_metadata=False):
    '''Note, keep metadata does not overwrite the exist destination'''
    try:
        if keep_metadata:
            shutil.copy2(f1, f2)
        else:
            shutil.copy(f1, f2)
    except shutil.Error as e:
        err_msg = "error: shutil.copy(%s, %s) failed: %s" % (f1, f2, e.strerror)
        global_logger.error(err_msg)
        return False
    return True

def getTimestamp():
    global TIMEZONE_EST
    now = datetime.datetime.now(TIMEZONE_EST)
    ts = now.strftime('%Y.%m.%d.%H.%M.%S.%f')
    return ts

def getTimestampSecond():
    global TIMEZONE_EST
    now = datetime.datetime.now(TIMEZONE_EST)
    ts = now.strftime('%Y.%m.%d.%H.%M.%S')
    return ts

def getTimestampPureNum():
    global TIMEZONE_EST
    now = datetime.datetime.now(TIMEZONE_EST)
    ts = now.strftime('%Y%m%d%H%M%S%f')
    return int(ts)

def getTimestampSecondPureNum():
    global TIMEZONE_EST
    now = datetime.datetime.now(TIMEZONE_EST)
    ts = now.strftime('%Y%m%d%H%M%S')
    return int(ts)

def generate_random_string(length):
    # Define the character set (letters and digits in this case)
    characters = string.ascii_letters + string.digits
    # Generate a random string of the given length
    random_string = ''.join(random.choices(characters, k=length))
    return random_string
