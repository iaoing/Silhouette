from abc import ABC, abstractmethod
import netifaces

class EnvBase(ABC):
    """docstring for EnvBase."""
    def __init__(self):
        pass

    '''
    Below methods are regarding VM management and VM setup
    '''
    def SSH_POOL_SIZE(self) -> int:
        '''number of ssh config items allowed'''
        return 1000

    def SSH_CONFIG_FILE(self) -> str:
        '''the ssh config file path'''
        return '/home/cc/.ssh/config'

    def SSH_KEY_FILE(self) -> str:
        '''the ssh key file path to access the vm'''
        return self.HOST_REPO_HOME() + '/codebase/scripts/fs_conf/sshkey/fast25_ae_vm'

    def GUEST_HOSTNAME(self) -> str:
        '''the guest's hostname configged in host's ssh config file'''
        return 'localhost'

    def GUEST_USERNAME(self) -> str:
        '''the guest's user name that will be logged in'''
        return 'bing'

    def GUEST_LOGIN_ALIAS(self) -> str:
        '''the guest's host name that will be logged in'''
        return 'fast25_ae'

    '''
    Below are the values for memcached
    '''
    def MEMCACHED_IP_ADDRESS_HOST(self):
        # the address to connect to Memcached on the host
        return '127.0.0.1'

    def MEMCACHED_IP_ADDRESS_GUEST(self):
        # The route address to connect to Memcached from guests.
        # This function should be only called in the guest script.
        # Run the 'ip route' command in the guest VM to obtain the default gateway address.
        gws=netifaces.gateways()
        return gws['default'][netifaces.AF_INET][0]

    def MEMCACHED_PORT(self):
        return '11211'

    '''
    Below are the values for remote time elapsed logging'''
    def ENABLE_TIME_LOG_SERVER(self)-> bool:
        return True

    def HOST_TIME_LOG_SEND_SERVER(self) -> bool:
        return False

    def GUEST_TIME_LOG_SEND_SERVER(self) -> bool:
        return True

    def TIME_LOG_SERVER_IP_ADDRESS_HOST(self):
        return self.MEMCACHED_IP_ADDRESS_HOST()

    def TIME_LOG_SERVER_IP_ADDRESS_GUEST(self):
        return self.MEMCACHED_IP_ADDRESS_GUEST()

    def TIME_LOG_SERVER_PORT(self):
        return 34543

    '''
    Below are the values for vm manager
    '''
    def RUN_LIMIT(self) -> int:
        '''number of vms, 0 indicates the number of cpus - 1'''
        return 0

    def BASE_IMG_FILE(self) -> str:
        '''the base qemu image file path'''
        return '/home/cc/silhouette_ae/qemu_imgs/silhouette_guest_vm_001.qcow2'

    def NUM_CPU(self) -> int:
        '''number of CPUs for a vm'''
        return 1

    def MEM_SIZE_GB(self) -> int:
        '''memory size for a vm'''
        return 8

    def DRAM_EMUILATED_PM_DEV(self) -> bool:
        '''
        If false, use a PM file to emulate PM dev.
        Otherwise, using kernel command line to emulate PM dev from DRAM, the BASE_PM_FILE will be ignored. Currently, Silhouette does not support to set the emulated PM dev size on host. Users need to start up the VM first, modify the kernel command line, update the grab, and then set the BASE_IMG_FILE.
        '''
        return True

    def BASE_PM_FILE(self) -> str:
        '''the base PM file path used for mounting as a PM device in vm'''
        # return '/mnt/pmem0/qemu/nvdimm.32m.img'
        # return '/mnt/ramfs/nvdimm.32m'
        # return '/mnt/ramfs/nvdimm.128m'
        return 'dram_emulated_pm_dev'

    def PM_SIZE_MB(self) -> int:
        '''
        The size of the PM file or the dram-emulated pm dev.
        The smallest device size affected by the file system type and the number of cores.
        '''
        return 128

    '''
    Below methods are regarding the using of RAMFS in the VM to store intermidiate data
    '''
    def GUEST_RAMFS_ENABLE(self) -> bool:
        return True

    def GUEST_RAMFS_MNT_POINT(self) -> str:
        '''
        The mount point of the RAMFS in the guest VM.
        Returns None if do not use ramfs.
        The ramfs can be used to store the intermidiate result and trace files,
        e.g., GUEST_RESULT_STORE_DIR, DUMP_TRACE_FUNC_FNAME, DUMP_TRACE_SV_FNAME
        '''
        return '/mnt/ramfs'

    def GUEST_RAMFS_SIZE(self) -> int:
        '''
        The size of ramfs in MiB.
        '''
        return 2048

    '''
    Below methods are regarding the file system mounting
    '''
    def MOD_DEV_PATH(self) -> str:
        '''the device path'''
        return '/dev/pmem0'

    def MOD_MNT_POINT(self) -> str:
        '''the fs mount point'''
        return '/mnt/pmem0'

    def MODULE_MAKE_DIR(self) -> str:
        '''the makefile dir for making the file system source code'''
        return "%s/codebase/trace/build-llvm15" % (self.GUEST_REPO_HOME())

    '''
    Below methods are regarding parameters of specific file systems
    '''
    @abstractmethod
    def MODULE_NAME(self) -> str:
        '''the file system name'''
        pass

    @abstractmethod
    def MOD_MNT_TYPE(self) -> str:
        '''the file system type to mount'''
        pass

    @abstractmethod
    def FS_MODULE_SRC_DIR(self) -> str:
        '''the file system source code dir'''
        pass

    @abstractmethod
    def MOD_INS_PARA(self) -> str:
        '''the fs module insert parameters'''
        pass

    @abstractmethod
    def MOD_MNT_PARA(self) -> str:
        '''the fs mount parameters'''
        pass

    @abstractmethod
    def MOD_REMNT_PARA(self) -> str:
        '''the fs remount parameters'''
        pass

    @abstractmethod
    def RUNTIME_TRACE_SRC(self) -> str:
        pass

    '''
    Below are regarding working directory
    '''
    def HOST_REPO_HOME(self) -> str:
        '''the dir of the silhouette codebase home on the host machine'''
        return '/home/cc/silhouette_ae/Silhouette'

    def GUEST_REPO_HOME(self) -> str:
        '''the dir of the silhouette codebase home on the guest machine'''
        return '/home/bing/workplace/Silhouette'

    def GUEST_LLVM15_HOME(self) -> str:
        '''the LLVM dir for instrumenting and build'''
        return '/home/bing/usr/local/llvm-15.0.0/rel'

    def HOST_RESULT_STORE_DIR(self) -> str:
        '''the dir for storing intermediate results (e.g., trace, crash plans)'''
        return '/tmp/sil'

    def GUEST_RESULT_STORE_DIR(self) -> str:
        '''the dir for storing intermediate results (e.g., trace, crash plans)'''
        if self.GUEST_RAMFS_ENABLE():
            return self.GUEST_RAMFS_MNT_POINT() + "/sil"
        else:
            return '/tmp/sil'

    '''
    below methods return the path that is in the guest
    '''
    def INFO_DUMP_EXE_DIR(self) -> str:
        return "%s/codebase/tools/src_info" % (self.GUEST_REPO_HOME())

    def INFO_DUMP_EXE(self) -> str:
        return "%s/codebase/tools/src_info/DumpSrcInfo" % (self.GUEST_REPO_HOME())

    def INFO_STRUCT_FNAME(self) -> str:
        return "%s/struct.info" % (self.FS_MODULE_SRC_DIR())

    def INFO_POSIX_FN_FNAME(self) -> str:
        return "%s/posix.func.info" % (self.FS_MODULE_SRC_DIR())

    def INFO_TRACE_FN_FNAME(self) -> str:
        return "%s/trace.func.info" % (self.FS_MODULE_SRC_DIR())

    def STRUCT_LAYOUT_EXE_DIR(self) -> str:
        return "%s/codebase/tools/struct_layout_ast" % (self.GUEST_REPO_HOME())

    def STRUCT_LAYOUT_EXE(self) -> str:
        return "%s/codebase/tools/struct_layout_ast/DumpStructLayout" % (self.GUEST_REPO_HOME())

    def STRUCT_LAYOUT_FNAME(self) -> str:
        return "%s/struct.layout.info" % (self.FS_MODULE_SRC_DIR())

    def DUMP_DISK_CONTENT_DIR(self) -> str:
        return "%s/codebase/tools/disk_content" % (self.GUEST_REPO_HOME())

    def DUMP_DISK_CONTENT_EXE(self) -> str:
        return "%s/codebase/tools/disk_content/DumpDiskContent" % (self.GUEST_REPO_HOME())

    def DUMP_TRACE_FUNC_FNAME(self) -> str:
        '''
        NOTE: this is hard-coded in Kernel tracing .c file.
        Please keep the one in the .c file matches the returned path here.
        '''
        if self.GUEST_RAMFS_ENABLE():
            return self.GUEST_RAMFS_MNT_POINT() + '/nova.inject.func.trace'
        else:
            return '/tmp/nova.inject.func.trace'

    def DUMP_TRACE_SV_FNAME(self) -> str:
        '''
        NOTE: this is hard-coded in Kernel tracing .c file.
        Please keep the one in that .c file matches the returned path here.
        '''
        if self.GUEST_RAMFS_ENABLE():
            return self.GUEST_RAMFS_MNT_POINT() + '/nova.inject.storevalue.trace'
        else:
            return '/tmp/nova.inject.storevalue.trace'

    def INSTID_SRCLOC_MAP_FPATH(self) -> str:
        return "%s/instid_srcloc_map.info" % (self.FS_MODULE_SRC_DIR())

    '''
    For workload.
    '''
    def EXEC_FILES(self) -> list:
        '''
        The files that need to be tested.
        The str in the list could be (a) a specific executable file path; (b) a path to a directory; (c) a regex path supportted by glob.
        For case (b) and (c), all matched executable files will be tested.
        NOTE: Silhouette uses basename to identify test cases, thus please make sure all test cases have different basenames.
        List of available bins:
        seq1_11func_bin         68
        seq2_11func_bin         4624
        seq3_11func_50k_bin     50000 out of 314432
        seq3_10func_50k_bin     50000 out of 175616
        dedup-seq3-11func-50k-nova-silhouette               368
        dedup-seq3-11func-50k-nova-silhouette-no-symlink    297
        dedup-seq3-11func-50k-pmfs-silhouette               285
        dedup-seq3-11func-50k-pmfs-silhouette-no-symlink    223
        dedup-seq3-11func-50k-winefs-silhouette             81
        dedup-seq3-11func-50k-winefs-silhouette-no-symlink  75
        codebase/workload/custom_workload/NOVA/snapshots
        codebase/workload/custom_workload/NOVA/page_links
        codebase/workload/custom_workload/common/append
        codebase/workload/custom_workload/common/long_file_name
        '''
        return ['/home/bing/seq1_11func_bin']
        # return [self.GUEST_REPO_HOME() + '/codebase/workload/custom_workload/common/append']

    '''
    For mapping the tested operation to the file system's operations
    '''
    @abstractmethod
    def FS_OP_MAP(self) -> dict:
        '''
        This could be determined by visiting vfs_op structures.
        TODO: traversing AST to build this map.
        '''
        pass

    @abstractmethod
    def IGNORE_STAT_ATTR_SET(self) -> set:
        '''
        Some attributes are always false in testing, ignore them to avoid crashing at the same attributes forever.
        '''
        pass
