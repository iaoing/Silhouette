"""kernel Module need to run, such as the NOVA, PMFS, etc."""
from abc import ABC, ABCMeta, abstractmethod

class ModuleMeta(ABCMeta):
    required_attributes = []

    def __call__(self, *args, **kwargs):
        obj = super(ModuleMeta, self).__call__(*args, **kwargs)
        for attr_name in obj.required_attributes:
            if not getattr(obj, attr_name):
                raise ValueError('required attribute (%s) not set' % attr_name)
        return obj

class ModuleBase(ABC, metaclass=ModuleMeta):
    TTL_BUILD_RAW = 300
    TTL_BUILD_INST = 600
    TTL_INSMOD = 20
    TTL_RMMOD = 20
    TTL_MOUNT = 20

    """docstring for ModuleBase."""
    required_attributes = ['name',  # name in string
                           'llvm15_home',
                           'src_dir',  # source directory, the built module located
                           'build_dir',  # build (Makefile) directory
                           'trace_src',
                           'info_exe',
                           'info_struct',
                           'info_posix',
                           'info_trace',
                           'struct_layout_exe',
                           'struct_layout_fname',
                           'instid_srcloc_map_fpath',
                           'mod_name',  # the module name (without the suffix .ko)
                           'insert_para',  # parameters for inserting module
                           'dev_path',  # the device to mount
                           'mnt_type',  # the FS type
                           'mnt_para',  # parameters for mounting FS
                           'remnt_para',  # parameters for mounting FS
                           'mnt_point',  # mount point
                           'guest_name',  # guest name for running ssh command
                           'user_name',
                           ]  #

    def __init__(self):
        # the derived class should set attributes in init function.
        pass

    @abstractmethod
    def build_raw_kobj(self) -> bool:
        '''build raw object'''
        pass

    @abstractmethod
    def build_instrument_kobj(self) -> bool:
        '''build instrument object'''
        pass

    @abstractmethod
    def insert_module(self) -> bool:
        '''insert FS module'''
        pass

    @abstractmethod
    def remove_module(self) -> bool:
        '''remove FS module'''
        pass

    @abstractmethod
    def mount_fs(self) -> bool:
        '''mount FS'''
        pass

    @abstractmethod
    def remount_fs(self) -> bool:
        '''remount FS'''
        pass

    @abstractmethod
    def chown_mnt_point(self) -> bool:
        '''change the ownship of the mnt point'''
        pass

    @abstractmethod
    def unmount_fs(self) -> bool:
        '''unmount FS'''
        pass

    def clean_mount(self) -> bool:
        '''umount, rmmod, insmod, and mount again'''
        self.unmount_fs()
        self.remove_module()
        if not self.insert_module():
            return False
        if not self.mount_fs():
            return False
        if not self.chown_mnt_point():
            return False
        return True
