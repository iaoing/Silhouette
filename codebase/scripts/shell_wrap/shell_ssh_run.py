import os
import sys
import subprocess

database_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(database_dir)

from scripts.shell_wrap.shell_cl_state import ShellCLState
from scripts.utils.logger import global_logger

LOCAL_RUN_TTL = 10

def shell_cl_ssh_run(cmd, host_name, ttl = LOCAL_RUN_TTL, crash_on_err = False):
    start_msg = "going to run a ssh command, ssh %s %s" % (host_name, cmd)
    end_msg = "end of running a ssh command, ssh %s %s" % (host_name, cmd)
    global_logger.debug(start_msg)

    cl_state = ShellCLState('ssh ' + host_name + " " + cmd)

    process = subprocess.Popen(['ssh', host_name, cmd],
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
    cl_state.proc = process

    global_logger.debug("pid: %d" % (process.pid))

    try:
        cl_state.stdout, cl_state.stderr = process.communicate(timeout=ttl)
    except subprocess.TimeoutExpired:
        # kill the process manually
        process.stderr.close()
        process.stdout.close()
        process.kill()
        process.wait()

        if crash_on_err:
            global_logger.critical(cl_state.msg("Timeout: "))
            assert False, cl_state.msg("Timeout: ")
        else:
            global_logger.warning(cl_state.msg("Timeout: "))
            global_logger.debug(end_msg)
            return cl_state


    cl_state.code = process.returncode
    if cl_state.code != 0:
        if crash_on_err:
            global_logger.critical(cl_state.msg())
            assert False, cl_state.msg()
        else:
            global_logger.warning(cl_state.msg())

    global_logger.debug(end_msg)
    return cl_state

