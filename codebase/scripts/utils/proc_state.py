import os, sys
import psutil

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.utils.logger import global_logger

def match_name_either(name : str, prefix = None, suffix = None, key_word = None) -> bool:
    # global_logger.debug("process name %s" % (name))
    if prefix:
        return name.startswith(prefix)
    elif suffix:
        return name.endswith(suffix)
    elif key_word:
        return key_word in name
    else:
        return False

def match_name_all(name : str, prefix = None, suffix = None, key_word = None) -> bool:
    if prefix and suffix and key_word:
        return name.startswith(prefix) and name.endswith(suffix) and key_word in name
    elif prefix and suffix:
        return name.startswith(prefix) and name.endswith(suffix)
    elif prefix and key_word:
        return name.startswith(prefix) and key_word in name
    elif suffix and key_word:
        return name.endswith(suffix) and key_word in name
    else:
        return match_name_either(name, prefix, suffix, key_word)

def match_proc_name(process, pid = None, full_name = None, prefix = None, suffix = None, key_word = None, match_all_pattern = True) -> bool:
    try:
        cmdline = " ".join(process.cmdline())
        if pid and process.pid() == pid:
            return True
        if full_name and cmdline == full_name:
            return True
        if match_all_pattern:
            if match_name_all(cmdline, prefix, suffix, key_word):
                return True
        else:
            if match_name_either(cmdline, prefix, suffix, key_word):
                return True
    except Exception as e:
        # sometime, it may arise error when get the name
        global_logger.warning("failed to get the name of a process, %s" % (str(process)))
        pass
    return False

def is_process_running(pid = None, full_name = None, prefix = None, suffix = None, key_word = None, match_all_pattern = True) -> bool:
    assert (full_name or prefix or suffix or key_word or pid), "invalid parameter"

    # log_msg = "check if the process is running " + str(pid) + str(full_name) + str(prefix) + str(suffix) + str(key_word) + str(match_all_pattern)
    # global_logger.debug(log_msg)

    for process in psutil.process_iter():
        try:
            if match_proc_name(process, pid, full_name, prefix, suffix, key_word, match_all_pattern):
                return True
        except Exception as e:
            # sometime, it may arise error when get the name
            # global_logger.debug("failed to get the name of a process, %s" % (str(process)))
            pass
    return False

def kill_process(pid = None, full_name = None, prefix = None, suffix = None, key_word = None, match_all_pattern = True) -> bool:
    assert (full_name or prefix or suffix or key_word or pid), "invalid parameter"

    log_msg = "going to kill process " + str(pid) + str(full_name) + str(prefix) + str(suffix) + str(key_word) + str(match_all_pattern)
    global_logger.debug(log_msg)

    for process in psutil.process_iter():
        try:
            if match_proc_name(process, pid, full_name, prefix, suffix, key_word, match_all_pattern):
                try:
                    process.kill()
                    process.wait(5)
                except psutil.TimeoutExpired:
                    global_logger.warning("timeout to kill a process, %s" % (str(process)))
                    return False
                return True
        except Exception as e:
            # global_logger.debug("failed to get the name of a process, %s" % (str(process)))
            pass

    global_logger.info("cannot find the process with given information")

    return False