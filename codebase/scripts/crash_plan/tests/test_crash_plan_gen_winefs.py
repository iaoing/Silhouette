import os
import sys
import logging
import pickle
from copy import copy

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(base_dir)

from scripts.tools_proc.struct_info_reader.struct_info_reader import StructInfoReader
from scripts.tools_proc.annot_reader.annot_reader import AnnotReader
from scripts.trace_proc.trace_reader.trace_reader import TraceReader
from scripts.trace_proc.trace_stinfo.stinfo_index import StInfoIndex
from scripts.trace_proc.trace_reader.trace_value_reader import TraceValueReader
from scripts.trace_proc.trace_split.vfs_op_trace_entry import OpTraceEntry
from scripts.trace_proc.trace_split.split_op_mgr import SplitOpMgr
from scripts.witcher.binary_file.binary_file import EmptyBinaryFile
from scripts.witcher.cache.witcher_cache import WitcherCache
from scripts.utils.logger import setup_global_logger
from scripts.utils.logger import global_logger
from logic_reason.mech.mech_undojnl.mech_undojnl_entry import MechUndoJnlEntry
from logic_reason.mech.mech_undojnl.mech_undojnl_reason import MechUndoJnlReason
from logic_reason.mech.mech_store.mech_pmstore_reason import MechPMStoreReason
from logic_reason.mech.mech_store.mech_cirtical_pmstore_reason import MechCirticalPMStoreReason
from logic_reason.mech.mech_link.mech_link_reason import MechLinkEntry, MechLinkReason
from logic_reason.mech.mech_lsw.mech_lsw_reason import MechLSWEntry, MechLSWReason
from logic_reason.mech.mech_memcpy.mech_memcpy_reason import MechMemcpyEntry, MechMemcpyReason
from logic_reason.mech.mech_replication.mech_repl_reason import MechReplEntry, MechReplReason
from logic_reason.crash_plan.crash_plan_gen import CrashPlanEntry, CrashPlanGenerator
from logic_reason.crash_plan.crash_plan_pm_data import CrashPlanPMData
from logic_reason.mech.mech_undojnl.mech_undojnl_cheat import MechUndoJnlCheat
from logic_reason.cheat_sheet.winefs.cheat_winefs import CheatSheetWinefs

def main(argc, argv):
    if argc != 5:
        print("usage: exe trace_file sv_file func_file stinfo_file")
        assert False, ("invalid arguments.")

    trace_file = argv[1]
    sv_file = argv[2]
    func_file = argv[3]
    stinfo_file = argv[4]

    setup_global_logger(fname="xx.log", file_lv=logging.DEBUG, stm=sys.stderr)

    trace_reader = TraceReader(trace_file)
    value_reader = TraceValueReader(sv_file)
    trace_reader.merge_value_entries(value_reader)

    func_annot = AnnotReader(func_file)

    stinfo_reader = StructInfoReader(stinfo_file)
    stinfo_index = StInfoIndex(trace_reader, stinfo_reader)

    winefs_cheat = CheatSheetWinefs()
    undo_jnl_cheat = MechUndoJnlCheat(trace_reader, stinfo_index, winefs_cheat)

    split_op_mgr = SplitOpMgr(trace_reader, func_annot)

    pm_data = CrashPlanPMData(trace_reader, value_reader)

    processed_set = set()
    count = 0
    for split_entry in split_op_mgr.op_entry_list:
        count += 1

        pm_id = str(split_entry.pm_op_id)
        if pm_id in processed_set:
            continue
        processed_set.add(pm_id)
        # pm_data.add_pm_id_num_list(split_entry.pm_op_id)

        pmstore_reason = MechPMStoreReason(split_entry)
        cstore_reason = MechCirticalPMStoreReason(split_entry, pmstore_reason)
        memcpy_reason = MechMemcpyReason(split_entry)
        link_reason = MechLinkReason(split_entry, pmstore_reason, stinfo_index)
        undojnl_reason = MechUndoJnlReason(split_entry, stinfo_index, pmstore_reason, cstore_reason, undo_jnl_cheat)
        lsw_reason = MechLSWReason(split_entry, stinfo_index, pmstore_reason,
                                   cstore_reason, undojnl_reason, link_reason)
        rep_reason = MechReplReason(split_entry, stinfo_index, pmstore_reason, memcpy_reason)
        print(split_entry.op_name)

        # generate in-flight cluster maps
        cache = WitcherCache(EmptyBinaryFile())
        split_entry.analysis_in_cache_run(cache)

        # undojnl_reason.dbg_print_detail()
        # lsw_reason.dbg_print_detail()
        # global_logger.debug(lsw_reason.dbg_get_detail())
        cp_gen = CrashPlanGenerator(split_entry, pmstore_reason, lsw_reason,
                                    rep_reason, undojnl_reason)

        cp_gen.dbg_print_detail()

        pickle_fname_base = "%s-%s" % (split_entry.op_name, count)
        cp_count = 0
        for cp in cp_gen.entry_list:
            cp_count += 1
            pickle_fname = "%s-%s-%d.pickle" % (pickle_fname_base, str(cp.type).split('.')[1], cp_count)
            print(pickle_fname)
            # with open(pickle_fname, 'wb') as f:
            #     pickle.dump(cp, f)

    # with open('pm_data.pickle', 'wb') as f:
    #     pickle.dump(pm_data, f)


if __name__ == "__main__":
    argc = len(sys.argv)
    argv = sys.argv
    main(argc, argv)
