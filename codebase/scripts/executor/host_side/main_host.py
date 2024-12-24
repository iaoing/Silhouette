import os
import sys
import argparse
from distutils.util import strtobool
import time
import time
import traceback
import re
import queue
from pymemcache.client.base import Client as CMClient
from pymemcache.client.base import PooledClient as CMPooledClient
from pymemcache import serde as CMSerde

codebase_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(codebase_dir)

from scripts.fs_conf.base.env_base import EnvBase
from scripts.fs_conf.base.env_phoney import EnvPhoney
from scripts.fs_conf.nova.env_nova import EnvNova
from scripts.fs_conf.pmfs.env_pmfs import EnvPmfs
from scripts.fs_conf.winefs.env_winefs import EnvWinefs
from scripts.fs_conf.base.module_default import ModuleDefault
from scripts.vm_comm.heartbeat_host import check_heartbeat_local
from scripts.shell_wrap.shell_ssh_run import shell_cl_ssh_run
from scripts.shell_wrap.shell_local_run import shell_cl_local_run
from scripts.utils.proc_state import kill_process
import scripts.shell_wrap.scp_wrap as ssh_copy
from scripts.vm_mgr.guest_state import GuestState
from scripts.vm_mgr.vm_mgr import SSHConfigPool
from scripts.vm_mgr.vm_mgr import VMMgr, VMInstance, VMConfig
import scripts.vm_comm.memcached_lock as mc_lock
from scripts.crash_plan.crash_plan_type import CrashPlanType
from scripts.executor.guest_side.tracing import TracingRstType
from scripts.executor.guest_side.validate_image import ValidateRstType
from scripts.executor.guest_side.deduce_mech import InvariantCheckErrorTypes
import scripts.vm_comm.memcached_wrapper as mc_wrapper
from scripts.utils.const_var import HEARTBEAT_INTERVAL
import scripts.utils.logger as log

def parse_args():
    parser = argparse.ArgumentParser(description='my args')

    parser.add_argument("--fs_type", type=str,
                        required=True,
                        help="NOVA/PMFS/WineFS.")
    parser.add_argument("--num_vms", type=int,
                        required=False, default=1,
                        help="The number of VMs.")
    parser.add_argument("--crash_plan_scheme", type=str,
                        required=True,
                        choices=['2cp', 'comb', 'mech2cp', 'mechcomb'],
                        help="The scheme to generate crash plans.")
    parser.add_argument("--debug_vm", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the VM will be terminated if the guest script raises a debug.")
    parser.add_argument("--stop_after_base_vm", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, this script will stop after the base VM is set-up. You can ssh the base VM to conduct other operations.")
    parser.add_argument("--stop_after_vms", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, this script will stop after number of VMs are set-up (running and snapshot created).")
    parser.add_argument("--clean_up_vm", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, spawned VMs will be killed.")
    parser.add_argument("--time_logger_local_file", type=str,
                        required=False, default=None,
                        help="The local logging file to store time elapsed information. If does not set, the time elapsed information will be logged in the logging file")
    parser.add_argument("--time_logger_server_file", type=str,
                        required=False, default=None,
                        help="The logging file to store time elapsed information received from remote clients.")
    parser.add_argument("--logging_file", type=str,
                        required=False, default=None,
                        help="The logging file")
    parser.add_argument("--logging_level", type=int,
                        required=False, default=40,
                        help="stderr output level:\n10: debug; 20: info ; 30: warning; 40: error; 50: critical. Default: 40.")
    parser.add_argument("--stderr_level", type=int,
                        required=False, default=50,
                        help="stderr output level:\n10: debug; 20: info ; 30: warning; 40: error; 50: critical. Default: 40.")

    # Below are some options that will be passed to the guest script.
    parser.add_argument("--num_cases_to_test", type=int,
                        required=False, default=sys.maxsize,
                        help="The number of test cases to run. Unlimited in default.")
    parser.add_argument("--test_case_basename", type=str,
                        required=False, default=None,
                        help="Specifically run this test case only. Will overwrite the number test-cases-to-test as 0. Other test cases in test_case_dir will be ignored.")
    parser.add_argument("--shuffle_test_cases", type=lambda x: bool(strtobool(x)),
                        required=False, default=True,
                        help="Shuffle test cases.")
    parser.add_argument("--shuffle_seed", type=int,
                        required=False, default=0x1234abcd,
                        help="The seed for randomly shuffle test cases.")
    parser.add_argument("--not_dedup", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the guest script will not proform the deduplication process.")
    parser.add_argument("--not_dedup_test_last", type=lambda x: bool(strtobool(x)),
                        required=False, default=True,
                        help="If enabled, the guest script will not proform the deduplication process and will only test the last meaningful operation of a test case. Only works when not_dedup is True.")
    parser.add_argument("--keep_intermidiate_result", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the intermidiate result (e.g., execution trace, crash plans) of each test case will be kept (be careful of the mount point space) in the guest VM.")
    parser.add_argument("--skip_umount", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, Silhouette skips the investigation of the umount function. Used for compare the running time with Chipmunk and Vinter since Chipmunk and Vinter do not test umount.")
    parser.add_argument("--stop_after_tracing", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the guest script runs only the execution-and-tracing phase. Other phases (e.g., deduplication, crash plan generation) will not be executed.")
    parser.add_argument("--stop_after_dedup", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the guest script runs the execution-and-tracing and the deduplication phases. Other phases (e.g., crash plan generation) will not be executed.")
    parser.add_argument("--stop_after_cache_sim", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the guest script runs the execution-and-tracing, the deduplication, and the cache simulating phases. Other phases (e.g., crash plan generation) will not be executed.")
    parser.add_argument("--stop_after_gen_crash_plan", type=lambda x: bool(strtobool(x)),
                        required=False, default=False,
                        help="If enabled, the guest script runs the execution-and-tracing, the deduplication, and the crash plan generation phases. Other phases (e.g., recovery and validation) will not be executed.")

    args = parser.parse_args()
    print(args)

    time_logger_local_file = args.time_logger_local_file
    time_logger_server_file = args.time_logger_server_file
    env = EnvPhoney()

    logging_file = args.logging_file
    logging_level = args.logging_level
    stderr_level = args.stderr_level

    if args.test_case_basename:
        args.num_cases_to_test = 0

    if time_logger_server_file and env.ENABLE_TIME_LOG_SERVER():
        log.log_server = log.LogRecordSelectorBasedStreamHandler(env.TIME_LOG_SERVER_IP_ADDRESS_HOST(), env.TIME_LOG_SERVER_PORT(), time_logger_server_file)
        log.log_server.serve_in_background()

    if env.HOST_TIME_LOG_SEND_SERVER():
        log.setup_global_logger(fname=logging_file, file_lv=logging_level, stm=sys.stderr, stm_lv=stderr_level, time_fname=time_logger_local_file, host=env.TIME_LOG_SERVER_IP_ADDRESS_HOST(), port=env.TIME_LOG_SERVER_PORT())

    else:
        log.setup_global_logger(fname=logging_file, file_lv=logging_level, stm=sys.stderr, stm_lv=stderr_level, time_fname=time_logger_local_file)

    return args

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        log.time_logger.info(f"elapsed_time.host.main.{func.__name__}:{time.perf_counter() - start_time:.6f}")
        return result
    return wrapper


def setup_env(fs_type):
    env = None
    if fs_type.upper() == 'NOVA':
        env = EnvNova()
    elif fs_type.upper() == 'PMFS':
        env = EnvPmfs()
    elif fs_type.upper() == 'WINEFS':
        env = EnvWinefs()
    else:
        log_msg = f"{traceback.format_exc()}\nInvalid file-system type: {fs_type}"
        log.global_logger.critical(log_msg)
        assert False, log_msg
    return env

class HostProc():
    def __init__(self, fs_type, num_vms, debug_vm, cp_scheme, args):
        self.args = args

        self.fs_type = fs_type
        self.env : EnvBase = setup_env(fs_type)
        self.num_vms = num_vms
        self.cp_scheme = cp_scheme
        self.debug_vm = debug_vm

        # sleep x second before poll the next vm state
        self.poll_vm_sleep_time = 1

        # since we do have use this client in multiple threads, set up a single client is okay.
        self.memcached_client : any[CMClient, CMPooledClient] = mc_wrapper.setup_memcached_client(self.env.MEMCACHED_IP_ADDRESS_HOST(), self.env.MEMCACHED_PORT(), vm_id='host_machine')
        # init some key-value pairs
        self._init_mc_kvs()

        # for checking heartbeat
        # if the elapsed heartbeats (seconds) between two heartbeats exceeds the ttl (datetime), considering a crash occurs on the guest.
        self.heartbeat_ttl = (num_vms * self.poll_vm_sleep_time) * 1.3 if num_vms > HEARTBEAT_INTERVAL else HEARTBEAT_INTERVAL * 2.3
        self.last_heartbeat_dict = dict()
        self.last_heartbeat_datetime_dict = dict()

        # for VM manager
        self.ssh_pool = SSHConfigPool(self.env)
        self.vm_mgr = VMMgr(env=self.env, ssh_config_pool=self.ssh_pool)

        # the base vm for prepareing environment for testing, e.g., compiling FS modules, prepare test cases, so that we do not need to redo some preparations if a crash occurs
        self.base_vm : VMInstance = None
        self._init_base_vm()
        if self.args.stop_after_base_vm:
            print("The base VM is set-up, stop at here.")
            if self.args.clean_up_vm:
                self.clear_vm()
            exit(0)

        # for tracking vm states.
        self.vm_instance_list = []
        self.vm_running_list = []
        self.vm_complete_list = []
        self.vm_broken_list = []
        self.vm_debug_list = []
        self._init_vm_instance()

        # set vm list so that we can get vm ids from Memcached and query the state for each one
        self._set_mc_vm_id_list()

        if self.args.stop_after_vms:
            print("All guest VMs are set-up, stop at here.")
            exit(0)

        self.guest_script = f'{self.env.GUEST_REPO_HOME()}/codebase/scripts/executor/guest_side/main_guest.py'

        # record the number of test cases that retested
        self.retest_case_dict = dict()
        # if a test case retested more than retest_threshold times, do not retest it.
        self.retest_threshold = 2

        # the seconds since starting the job, key is vm id
        # can be used to monitor whether the job is stucking in 'initing' state
        self.second_since_job_start_dict = dict()
        # the second since job start exceed the threshold, restart the vm rather than restore snapshot
        self.SECOND_TO_RESTART_VM_SINCE_JOB_START = 180

        # recording the heartbeat and the datetime of that heartbeat, so that we can compute the elapsed time between two checks and the elapsed heartbeats
        self.last_heartbeat_dict = dict()
        self.last_heartbeat_datetime_dict = dict()

    @timeit
    def _init_mc_kvs(self):
        # clean up memcached
        self.memcached_client.flush_all()

        # set key-value pairs
        key = 'next_exec_list_index'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)
        key = 'unique_case_count'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)
        key = 'failed_case_count'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)
        key = 'failed_ctx_case_count'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)
        key = 'failed_umount_case_count'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)
        key = 'id_seq_set'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, set())
        key = 'id_seq_set_lock'
        mc_lock.init_lock(self.memcached_client, key)
        key = 'vm_id_list'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, list())

        # for storing performance analysis (e.g., number of in-flight store, number of duplicate fences)
        key = 'cache_sim_result_count'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)

        # for storing the crash plan and validate result for a given operation in a test case
        key = 'crash_plan_to_validate_rst'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)

        # for tracing error result
        for tp in TracingRstType:
            key = f'TracingRstType.{tp.value}.count'
            mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)

        # for invariant check result
        for tp in InvariantCheckErrorTypes:
            key = f'InvariantCheckErrorTypes.{tp.value}.count'
            mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)

        # for number of generated crash plans
        for tp in CrashPlanType:
            key = f'CrashPlanType.{tp.value}.count'
            mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)

        # for validation result
        for tp in ValidateRstType:
            key = f'ValidateRstType.{tp.value}.count'
            mc_wrapper.mc_set_wrapper(self.memcached_client, key, 0)

    @timeit
    def _init_base_vm(self):
        self.base_vm : VMInstance = self.vm_mgr.create_vm()
        tmp_base_fs = ModuleDefault(self.env, self.base_vm.ssh_config.alias_name, local_run=False)

        # 1. start vm
        self.base_vm.start()
        ret = self.base_vm.wait_until_access_ok(ttw=120)
        assert ret, "cannot access the vm"

        # 2. create guest dir for storing the codebase
        cmd = f'mkdir -p {self.env.GUEST_REPO_HOME()}'
        cl_state = shell_cl_ssh_run(cmd, self.base_vm.ssh_config.alias_name, ttl=60)
        assert cl_state.code == 0, "create guest dir failed"

        # 3. copy repository
        ret = ssh_copy.copy_dir_to_guest(host_dir=self.env.HOST_REPO_HOME() + "/*", guest_name=self.base_vm.ssh_config.alias_name, guest_dir=self.env.GUEST_REPO_HOME() + "/", ttl=3000, assert_at_failure=False)
        assert ret, "copy repo to guest failed"

        # 4. build the info dump execution
        cmd = f'make -C {self.env.INFO_DUMP_EXE_DIR()} LLVM15_HOME={self.env.GUEST_LLVM15_HOME()}'
        cl_state = shell_cl_ssh_run(cmd, self.base_vm.ssh_config.alias_name, ttl=60)
        assert cl_state.code == 0, "make dump disk content execution failed"

        # 5. build structure layout dump execution
        cmd = f'make -C {self.env.STRUCT_LAYOUT_EXE_DIR()} LLVM15_HOME={self.env.GUEST_LLVM15_HOME()}'
        cl_state = shell_cl_ssh_run(cmd, self.base_vm.ssh_config.alias_name, ttl=60)
        assert cl_state.code == 0, "make struct info annotation execution failed"

        # 6. prep instrumented file system module
        ret = tmp_base_fs.build_instrument_kobj()
        assert ret, "build_instrument_kobj failed"

        # 7. prep raw file system module
        ret = tmp_base_fs.build_raw_kobj()
        assert ret, "build_raw_kobj failed"

        if not self.args.stop_after_base_vm:
            # the vm is the base one to avoid re-prepare modules, executables.
            ret = self.base_vm.terminal()
            assert ret, "vm terminal failed"

    @timeit
    def _init_vm_instance(self):
        for _ in range(self.num_vms):
            vm_instance = self.vm_mgr.create_vm(father_config=self.base_vm.vm_config)
            self.vm_instance_list.append(vm_instance)
            if not vm_instance.start():
                msg = f"start {str(vm_instance.vm_config)} failed"
                log.global_logger.critical(msg)
                assert False, msg

        for vm in self.vm_instance_list:
            vm : VMInstance
            if not vm.wait_until_access_ok(ttw=120):
                msg = f"wait_until_access_ok {str(vm.vm_config)} failed"
                log.global_logger.critical(msg)
                assert False, msg

            # This vm is accessible, adding to the running list.
            self.vm_running_list.append(vm)

            # Create a snapshot so that we can restore it instead of restart it.
            # Creating a snapshot is a async cmd, which may take some seconds.
            # Wait until can be accessible
            # TODO: async creating snapshot, so that we do not need to wait at here.
            msg = f'begin create snapshot {vm.ssh_config.alias_name}'
            log.global_logger.debug(msg)
            vm.create_snapshot()

    @timeit
    def _set_mc_vm_id_list(self):
        vm_id_list = []
        for vm in self.vm_running_list:
            vm : VMInstance
            vm_id_list.append(vm.ssh_config.alias_name)

        key = 'vm_id_list'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, vm_id_list)

    @timeit
    def _start_guest_job(self, host_name, vm_id, test_case_basename=None):
        if self.args.test_case_basename:
            test_case_basename = self.args.test_case_basename
            # Avoid forever loops
            self.args.test_case_basename = None

        cmd = (
            f'nohup sudo python3 {self.guest_script} '
            f'--fs_type={self.fs_type} '
            f'--crash_plan_scheme {self.cp_scheme} '
            f'--test_case_basename {test_case_basename} '
            f'--vm_id {vm_id} '
            f'--num_cases_to_test {self.args.num_cases_to_test} '
            f'--shuffle_test_cases {self.args.shuffle_test_cases} '
            f'--shuffle_seed {self.args.shuffle_seed} '
            f'--not_dedup {self.args.not_dedup} '
            f'--not_dedup_test_last {self.args.not_dedup_test_last} '
            f'--keep_intermidiate_result {self.args.keep_intermidiate_result} '
            f'--skip_umount {self.args.skip_umount} '
            f'--stop_after_tracing {self.args.stop_after_tracing} '
            f'--stop_after_dedup {self.args.stop_after_dedup} '
            f'--stop_after_cache_sim {self.args.stop_after_cache_sim} '
            f'--stop_after_gen_crash_plan {self.args.stop_after_gen_crash_plan} '
            f'--logging_file /tmp/log.guest '
            f'--logging_level 10 '
            '1>>/tmp/log.nohup 2>>/tmp/log.nohup &'
        )

        cl_state = shell_cl_ssh_run(cmd, host_name=host_name, ttl=30, crash_on_err=False)
        if cl_state.code != 0:
            msg = f'{cl_state.msg("run guest dedup failed: ")}'
            log.global_logger.error(msg)
            return False

        key = f'{vm_id}.state'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, GuestState.STARTED)
        self.second_since_job_start_dict[vm_id] = int(time.perf_counter())

        return True

    def _get_vm_state(self, vm : VMInstance) -> GuestState:
        vm_id = vm.ssh_config.alias_name
        key = f'{vm_id}.state'
        value : GuestState = mc_wrapper.mc_get_wrapper(self.memcached_client, key)
        return value

    def _reset_heartbeat(self, vm : VMInstance):
        vm_id = vm.ssh_config.alias_name
        self.last_heartbeat_dict[vm_id] = None
        self.last_heartbeat_datetime_dict[vm_id] = None
        key = f'heartbeat.{vm_id}'
        mc_wrapper.mc_set_wrapper(self.memcached_client, key, None)

    def _check_heartbeat(self, vm : VMInstance):
        vm_id = vm.ssh_config.alias_name
        heartbeat_key = f'heartbeat.{vm_id}'
        ret, self.last_heartbeat_dict[vm_id], self.last_heartbeat_datetime_dict[vm_id] = check_heartbeat_local(self.memcached_client, heartbeat_key, self.last_heartbeat_dict[vm_id], self.last_heartbeat_datetime_dict[vm_id], timeout=self.heartbeat_ttl)
        return ret

    @timeit
    def _restore_vm(self, vm : VMInstance):
        vm_id = vm.ssh_config.alias_name
        msg = f"restoring vm {vm_id}"
        log.global_logger.debug(msg)
        vm.restore_snapshot()
        return True

    @timeit
    def _restart_vm(self, vm : VMInstance):
        vm_id = vm.ssh_config.alias_name
        msg = f"restarting vm {vm_id}"
        log.global_logger.debug(msg)
        if not vm.restart_if_cannot_access(force=True):
            # restart the vm
            msg = f'restart {vm_id} failed'
            log.global_logger.error(msg)
            return False
        else:
            return True

    @timeit
    def _restore_job(self, vm : VMInstance, retest : bool = True):
        ret = False
        vm_id = vm.ssh_config.alias_name
        test_case_basename = None

        if retest:
            # get the test case that need to be retested
            key = f'{vm_id}.start'
            v1 = mc_wrapper.mc_get_wrapper(self.memcached_client, key)
            key = f'{vm_id}.end'
            v2 = mc_wrapper.mc_get_wrapper(self.memcached_client, key)

            if isinstance(v1, list) and len(v1) == 2 and v2 == None:
                test_case_basename = v1[0]
            elif isinstance(v1, list) and len(v1) == 2 and isinstance(v2, list) and len(v2) == 2:
                if v1[0] == v2[0]:
                    # this test case has been done
                    pass
                else:
                    test_case_basename = v1[0]

        # restart the guest dedup script
        if test_case_basename:
            if test_case_basename not in self.retest_case_dict:
                self.retest_case_dict[test_case_basename] = 0

            if self.retest_case_dict[test_case_basename] < self.retest_threshold:
                msg = f"retest {test_case_basename} {self.retest_case_dict[test_case_basename]} times on {vm_id}"
                log.global_logger.debug(msg)
                ret = self._start_guest_job(vm_id, vm_id, test_case_basename)
                self.retest_case_dict[test_case_basename] += 1
            else:
                # exceed the limit, do not retest it
                ret = self._start_guest_job(vm_id, vm_id)

        else:
            # did not find the case that needs to be retested
            ret = self._start_guest_job(vm_id, vm_id)

        return ret

    @timeit
    def start_all_jobs(self):
        for vm in self.vm_running_list:
            vm : VMInstance
            vm_id = vm.ssh_config.alias_name
            self._reset_heartbeat(vm)
            ret = self._start_guest_job(vm_id, vm_id)
            if not ret:
                assert False, f"start job failed on {vm_id}"

    @timeit
    def monitor_jobs(self):
        while True:
            if len(self.vm_running_list) == 0:
                break

            for vm in self.vm_running_list:
                vm : VMInstance
                vm_id = vm.ssh_config.alias_name

                time.sleep(1)

                # 1. check state
                vm_state = self._get_vm_state(vm)
                if vm_state == GuestState.STARTED:
                    if time.perf_counter() - self.second_since_job_start_dict[vm_id] > self.SECOND_TO_RESTART_VM_SINCE_JOB_START:
                        if not self._restart_vm(vm):
                            self.vm_broken_list.append(vm)
                            self.vm_running_list.remove(vm)
                            break
                        else:
                            self._reset_heartbeat(vm)
                            if not self._restore_job(vm):
                                self.vm_broken_list.append(vm)
                                self.vm_running_list.remove(vm)
                                break
                            else:
                                continue
                    else:
                        continue

                elif vm_state == GuestState.INITING:
                    pass

                elif vm_state == GuestState.RUNNING:
                    pass

                elif vm_state == GuestState.COMPLETE:
                    self.vm_complete_list.append(vm)
                    self.vm_running_list.remove(vm)
                    break

                elif vm_state == GuestState.NEED_RESTORE_SNAPSHOT:
                    self._restore_vm(vm)
                    self._reset_heartbeat(vm)
                    if not self._restore_job(vm):
                        self.vm_broken_list.append(vm)
                        self.vm_running_list.remove(vm)
                        break
                    else:
                        continue

                elif vm_state == GuestState.NEED_RESTART_VM:
                    if not self._restart_vm(vm):
                        self.vm_broken_list.append(vm)
                        self.vm_running_list.remove(vm)
                        break
                    else:
                        self._reset_heartbeat(vm)
                        if not self._restore_job(vm):
                            self.vm_broken_list.append(vm)
                            self.vm_running_list.remove(vm)
                            break
                        else:
                            continue
                        continue

                elif vm_state == GuestState.VALIDATION_FAILED:
                    self._restore_vm(vm)
                    self._reset_heartbeat(vm)
                    # if the test case is failed in validation, do not need to test it again, go to the next test case
                    if not self._restore_job(vm, retest=False):
                        self.vm_broken_list.append(vm)
                        self.vm_running_list.remove(vm)
                        break
                    else:
                        continue

                elif vm_state == GuestState.NEED_DEBUG:
                    if self.debug_vm:
                        self.vm_debug_list.append(vm)
                        self.vm_running_list.remove(vm)
                        break
                    else:
                        self._restore_vm(vm)
                        self._reset_heartbeat(vm)
                        if not self._restore_job(vm):
                            self.vm_broken_list.append(vm)
                            self.vm_running_list.remove(vm)
                            break
                        else:
                            continue

                else:
                    # NOT_STARTED, UNKNOWN
                    msg = f"invalid state: {vm_id} state is {vm_state}"
                    log.global_logger.error(msg)
                    self.vm_broken_list.append(vm)
                    self.vm_running_list.remove(vm)
                    break

                # 2. check heartbeat
                if not self._check_heartbeat(vm):
                    self._restore_vm(vm)
                    self._reset_heartbeat(vm)
                    if not self._restore_job(vm):
                        self.vm_broken_list.append(vm)
                        self.vm_running_list.remove(vm)
                        break
                    else:
                        continue

        msg = f'retested cases: {str(self.retest_case_dict)}'
        log.global_logger.debug(msg)

    def clear_vm(self):
        self.vm_mgr.destory()
        self.vm_mgr.reclaim_resource()
        self.ssh_pool.destory_pool()
        log_msg = 'All VMs are cleaned up.'
        log.global_logger.debug(log_msg)

@timeit
def main(args):
    fs_type = args.fs_type
    num_vms = args.num_vms
    cp_scheme = args.crash_plan_scheme
    debug_vm = args.debug_vm

    host_proc = HostProc(fs_type, num_vms, debug_vm, cp_scheme, args)
    host_proc.start_all_jobs()
    host_proc.monitor_jobs()

    if args.clean_up_vm:
        host_proc.clear_vm()

if __name__ == "__main__":
    args = parse_args()
    main(args)
