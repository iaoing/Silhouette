"""
Used to allocate ssh port and update ssh config file
"""
import os, sys
import threading

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(codebase_dir)

import scripts.utils.utils as my_utils
from scripts.fs_conf.base.env_base import EnvBase
from scripts.vm_mgr.socket_port import find_first_available_port
from scripts.utils.logger import global_logger

class SSHConfig:
    def __init__(self) -> None:
        self.port = None
        # alias name used for ssh (e.g., ssh alias_name command)
        self.alias_name = None

    def __str__(self):
        return "port: %d, alias name: %s" % \
                (self.port, self.alias_name)

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other) -> bool:
        return isinstance(other, SSHConfig) and \
               self.port == other.port and \
               self.alias_name == other.alias_name

class SSHConfigPool:
    """
    Config pool only maintain the ssh and config file.
    """
    def __init__(self, env : EnvBase) -> None:
        self.pool_size = env.SSH_POOL_SIZE()
        self.guest_addr = env.GUEST_HOSTNAME()
        self.user_name = env.GUEST_USERNAME()
        self.ssh_config_file = env.SSH_CONFIG_FILE()
        self.ssh_key_file = env.SSH_KEY_FILE()
        self.guest_alias_name = env.GUEST_LOGIN_ALIAS()

        self.destoried = False

        # this is used to identity the unique configration generated by this class
        self.id_str = my_utils.getTimestamp()

        # backup the config file
        self.backup_ssh_config_file = self.ssh_config_file + "." + self.id_str + ".bak"

        # use lock to control the cirtical section.
        self.lock = threading.Lock()

        # first in first out list
        # to avoid port conflicts, we do not make configuration until needed.
        self.free_pool = []
        self.using_pool = []

        self.__backup_ssh_config_file()

    def __backup_ssh_config_file(self):
        if not my_utils.fileExists(self.ssh_config_file):
            my_utils.createFile(self.ssh_config_file)
        if not my_utils.copyFile(self.ssh_config_file, self.backup_ssh_config_file):
            err_msg = "copy %s as %s failed" % (self.ssh_config_file, self.backup_ssh_config_file)
            global_logger.error(err_msg)
            assert False, global_logger

    def __gen_ssh_config_file_content(self, conf : SSHConfig):
        data = "\nHost %s\n" % (conf.alias_name)
        data += "    Hostname %s\n" % (self.guest_addr)
        data += "    Port %d\n" % (conf.port)
        data += "    User %s\n" % (self.user_name)
        data += "    IdentityFile %s\n" % (self.ssh_key_file)
        data += "    IdentitiesOnly Yes\n"
        data += "    StrictHostKeyChecking no\n"
        data += "# %s\n" % (self.id_str)
        return data

    def __config_exist_in_ssh_file(self, conf : SSHConfig) -> bool:
        fd = open(self.ssh_config_file, 'r')
        ctx = fd.read()
        fd.close()

        host_name = "Host %s" % (conf.alias_name)
        if host_name in ctx:
            return True
        else:
            return False

    def __add_to_ssh_config_file(self, conf) -> bool:
        if self.__config_exist_in_ssh_file(conf):
            err_mgs = ("%s is already in the ssh config file" % (str(conf)))
            global_logger.error(err_mgs)
            assert False, err_mgs

        data = self.__gen_ssh_config_file_content(conf)

        fd = open(self.ssh_config_file, 'a+')
        fd.write(data)
        fd.close()

        log_msg = "ssh config content is added to ssh config file, %s" % (data)
        global_logger.debug(log_msg)

        return True

    def __remove_from_ssh_config_file(self, conf) -> bool:
        if not self.__config_exist_in_ssh_file(conf):
            global_logger.warning("%s is not in the ssh config file" % (str(conf)))
            return True

        data = self.__gen_ssh_config_file_content(conf)
        fd = open(self.ssh_config_file, 'r')
        ctx = fd.read()
        fd.close()

        if data not in ctx:
            global_logger.error("%s is in the ssh config file, but does not match the config data, %s" % (str(conf), data))
            return False
        ctx.replace(data, "")

        fd = open(self.ssh_config_file, 'w')
        fd.seek(0)
        fd.write(ctx)
        fd.truncate()
        fd.close()

        log_msg = "ssh config content is removed to ssh config file, %s" % (data)
        global_logger.debug(log_msg)

        return True

    def __generate_ssh_config(self) -> SSHConfig:
        """
        Required: lock is hold
        """
        port = find_first_available_port()
        if port < 0:
            global_logger.error("does not get an available port number")
            return None

        conf = SSHConfig()
        conf.port = port
        conf.alias_name = "%s%d" % (self.guest_alias_name, port)

        self.__add_to_ssh_config_file(conf)

        log_msg = "new conf added to ssh config file: %s" % (str(conf))
        global_logger.debug(log_msg)

        return conf

    def alloc_ssh_config(self) -> SSHConfig:
        """return None if not free config"""
        conf = None
        self.lock.acquire()

        if len(self.using_pool) >= self.pool_size:
            global_logger.info("using ssh config touch the pool threshold %d %d" % (len(self.using_pool), self.pool_size))
            pass
        else:
            if len(self.free_pool) > 0:
                conf = self.free_pool[0]
                if conf:
                    self.free_pool.pop(0)
            else:
                conf = self.__generate_ssh_config()
                self.using_pool.append(conf)

        self.lock.release()
        return conf

    def dealloc_ssh_config(self, conf : SSHConfig):
        self.lock.acquire()

        if conf in self.using_pool:
            self.using_pool.remove(conf)
        else:
            log_msg = "ssh config is not is using pool, %s" % (str(conf))
            global_logger.debug(log_msg)

        if conf not in self.free_pool:
            self.free_pool.append(conf)
        else:
            log_msg = "ssh config is already is free pool, %s" % (str(conf))
            global_logger.debug(log_msg)

        self.lock.release()

    def destory_pool(self):
        if self.destoried:
            return True

        for ssh in self.free_pool:
            self.__remove_from_ssh_config_file(ssh)

        if len(self.using_pool) > 0:
            log_msg = ("still have ssh config in using:\n")
            for ssh in self.using_pool:
                log_msg += str(ssh) + ";"
            log_msg += "\n"
            global_logger.warning(log_msg)
            return False
        else:
            # resume the backup file
            log_msg = "resume the origin ssh config file %s %s" % (self.backup_ssh_config_file, self.ssh_config_file)
            global_logger.debug(log_msg)

            if not my_utils.copyFile(self.backup_ssh_config_file, self.ssh_config_file):
                err_msg = "copy %s as %s failed" % (self.backup_ssh_config_file, self.ssh_config_file)
                global_logger.error(err_msg)
                assert False, global_logger

            log_msg = "remove backup ssh config file, %s" % (self.backup_ssh_config_file)
            global_logger.debug(log_msg)

            if not my_utils.removeFile(self.backup_ssh_config_file):
                log_msg = "remove backup ssh config file failed, %s" % (self.backup_ssh_config_file)
                global_logger.warning(log_msg)

            self.destoried = True
            return True
