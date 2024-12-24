import os
import sys

scripts_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../../.."))
sys.path.append(scripts_dir)

from scripts.cheat_sheet.base.cheat_base import CheatSheetBase
from scripts.cheat_sheet.base.cheat_base import UndoJnlCheatSheetBase
from scripts.cheat_sheet.base.cheat_base import LSWCheatSheetBase
from scripts.cheat_sheet.base.cheat_base import RepCheatSheetBase
from scripts.cheat_sheet.base.cheat_base import LinkedListCheatSheetBase


class UndoJnlCheatSheet(UndoJnlCheatSheetBase):
    def __init__(self):
        super().__init__()

        self.pre_alloc : bool = True

        self.circular_buf_addr : list = ['pmfs_journal.base.unsigned']
        self.circular_buf_size : list = ['pmfs_journal.size.unsigned']

        self.head : list = ['pmfs_journal.head.unsigned', 'pmfs_journal.base.unsigned', '+']
        self.tail : list = ['pmfs_journal.tail.unsigned', 'pmfs_journal.base.unsigned', '+']

        self.tx_commit_var : list = ['pmfs_logentry_t.type.unsigned']
        self.tx_commit_var_val : int = 2

        self.log_entry_struct : list = ['pmfs_logentry_t']
        self.logged_addr : list = ['pmfs_logentry_t.addr_offset.unsigned']
        self.logged_size : list = ['pmfs_logentry_t.size.unsigned']
        self.logged_data :  list = ['pmfs_logentry_t.data.unsigned']
        self.logging_commit : list = ['pmfs_logentry_t.gen_id.unsigned']

class CheatSheetWineFS(CheatSheetBase):
    def __init__(self):
        super().__init__()
        self.filesystem : str = 'winefs'
        self.undo_jnl_sheet : UndoJnlCheatSheetBase = UndoJnlCheatSheet()
        self.lsw_sheet_list : list = []
        self.rep_sheet : RepCheatSheetBase = None
        self.link_sheet : LinkedListCheatSheetBase = None
