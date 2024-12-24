"""
Generate shell command in string.
The command could be passed to popen or other functions to execute.
"""

def shell_cl_sudo(cmd=''):
    return "sudo " + cmd

def shell_cl_true():
    return 'true'

def shell_cl_file_exist(fname):
    return '[ -f %s ]' % (fname)

def shell_cl_dir_exist(path):
    return '[ -d %s ]' % (path)

def shell_cl_dev_exist(dev):
    return '[ -b %s ]' % (dev)

def shell_cl_mkdir(path, opt=''):
    return 'mkdir %s %s' % (opt, path)

def shell_cl_rmdir(path, opt=''):
    return 'rmdir %s %s' % (opt, path)

def shell_cl_rm(fname, opt=''):
    return 'rmdir %s %s' % (opt, fname)

def shell_cl_cat(fname):
    return 'cat %s' % (fname)

def shell_cl_dmesg():
    return 'dmesg'

def shell_cl_dmesg_clear():
    return 'dmesg -C'
