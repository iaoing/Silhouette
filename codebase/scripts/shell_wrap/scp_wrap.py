"""Represent the return values from a shell running"""
import os
import sys

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.utils.logger import global_logger

def copy_file_to_guest(host_fname, guest_name, guest_dir, ttl, assert_at_failure = True):
    '''scp host dir under guest dir'''
    cmd = "scp -r %s %s:%s/" % (host_fname, guest_name, guest_dir)

    global_logger.debug("%s" % (cmd))

    cl_state = shell_cl_local_run(cmd, ttl)

    global_logger.debug("%s" % (cl_state.msg()))

    if cl_state.code != 0:
        err_msg = "execution failed, %s" % (cl_state.msg())
        global_logger.error(err_msg)
        if assert_at_failure:
            assert False, err_msg

    return cl_state.code == 0

def copy_file_to_guest_as(host_fname, guest_name, guest_fname, ttl, assert_at_failure = True):
    '''scp host dir under guest dir'''
    cmd = "scp -r %s %s:%s" % (host_fname, guest_name, guest_fname)

    global_logger.debug("%s" % (cmd))

    cl_state = shell_cl_local_run(cmd, ttl)

    global_logger.debug("%s" % (cl_state.msg()))

    if cl_state.code != 0:
        err_msg = "execution failed, %s" % (cl_state.msg())
        global_logger.error(err_msg)
        if assert_at_failure:
            assert False, err_msg

    return cl_state.code == 0

def copy_file_to_host(host_dir, guest_name, guest_fname, ttl, assert_at_failure = True):
    '''scp host dir under guest dir'''
    cmd = "scp -r %s:%s %s/" % (guest_name, guest_fname, host_dir)

    global_logger.debug("%s" % (cmd))

    cl_state = shell_cl_local_run(cmd, ttl)

    global_logger.debug("%s" % (cl_state.msg()))

    if cl_state.code != 0:
        err_msg = "execution failed, %s" % (cl_state.msg())
        global_logger.error(err_msg)
        if assert_at_failure:
            assert False, err_msg

    return cl_state.code == 0

def copy_file_to_host_as(host_fname, guest_name, guest_fname, ttl, assert_at_failure = True):
    '''scp host dir under guest dir'''
    cmd = "scp -r %s:%s %s" % (guest_name, guest_fname, host_fname)

    global_logger.debug("%s" % (cmd))

    cl_state = shell_cl_local_run(cmd, ttl)

    global_logger.debug("%s" % (cl_state.msg()))

    if cl_state.code != 0:
        err_msg = "execution failed, %s" % (cl_state.msg())
        global_logger.error(err_msg)
        if assert_at_failure:
            assert False, err_msg

    return cl_state.code == 0

def copy_dir_to_guest(host_dir, guest_name, guest_dir, ttl, assert_at_failure = True):
    '''scp host dir under guest dir'''
    cmd = "scp -r %s %s:%s/" % (host_dir, guest_name, guest_dir)

    global_logger.debug("%s" % (cmd))

    cl_state = shell_cl_local_run(cmd, ttl)

    global_logger.debug("%s" % (cl_state.msg()))

    if cl_state.code != 0:
        err_msg = "execution failed, %s" % (cl_state.msg())
        global_logger.critical(err_msg)
        if assert_at_failure:
            assert False, err_msg

    return cl_state.code == 0

def copy_dir_to_host(host_dir, guest_name, guest_dir, ttl, assert_at_failure = True):
    '''scp host dir under guest dir'''
    cmd = "scp -r %s:%s %s/" % (guest_name, guest_dir, host_dir)

    global_logger.debug("%s" % (cmd))

    cl_state = shell_cl_local_run(cmd, ttl)

    global_logger.debug("%s" % (cl_state.msg()))

    if cl_state.code != 0:
        err_msg = "execution failed, %s" % (cl_state.msg())
        global_logger.error(err_msg)
        if assert_at_failure:
            assert False, err_msg

    return cl_state.code == 0

