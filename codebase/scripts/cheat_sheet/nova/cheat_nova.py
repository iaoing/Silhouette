import os
import sys

scripts_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../../.."))
sys.path.append(scripts_dir)

from scripts.cheat_sheet.base.cheat_base import LinkedListCheatSheetBase
from scripts.cheat_sheet.base.cheat_base import RepCheatSheetBase
from scripts.cheat_sheet.base.cheat_base import LSWCheatSheetBase
from scripts.cheat_sheet.base.cheat_base import UndoJnlCheatSheetBase
from scripts.cheat_sheet.base.cheat_base import CheatSheetBase

class UndoJnlCheatSheet(UndoJnlCheatSheetBase):
    def __init__(self):
        super().__init__()

        self.pre_alloc : bool = False

        self.circular_buf_addr : list = ['journal_ptr_pair.journal_head.unsigned']
        # the circurlar buffer is one block, 4096 bytes
        self.circular_buf_size : list = [4096]

        self.head : list = ['journal_ptr_pair.journal_head.unsigned']
        self.tail : list = ['journal_ptr_pair.journal_tail.unsigned']

        self.log_entry_struct : list = ['nova_lite_journal_entry']
        self.logged_addr : list = ['nova_lite_journal_entry.data1.unsigned']
        # 8 bytes or 120 bytes depends on the type
        # 232 - 112 * type
        # type can only be 1 or 2 in NOVA
        self.logged_size : list = [232, 112, 'nova_lite_journal_entry.type.unsigned', '*', '-']
        self.logged_data :  list = ['nova_lite_journal_entry.data2.unsigned']
        self.logging_commit : list = None

class LSWCheatSheet1(LSWCheatSheetBase):
    def __init__(self):
        super().__init__()

        self.tail : list = ['nova_inode.log_tail.unsigned']
        # one block
        self.log_space_size = [4096]
        self.pre_alloc : bool = False

class LSWCheatSheet2(LSWCheatSheetBase):
    def __init__(self):
        super().__init__()

        self.tail : list = ['nova_inode.alter_log_tail.unsigned']
        # one block
        self.log_space_size = [4096]
        self.pre_alloc : bool = False

class RepCheatSheet(RepCheatSheetBase):
    def __init__(self):
        super().__init__()

        self.struct_set : set = {
                'nova_inode',
                'nova_file_write_entry',
                'nova_dentry',
                'nova_setattr_logentry',
                'nova_link_change_entry',
            }
        self.num_rep : int = 2

class LinkedListCheatSheet(LinkedListCheatSheetBase):
    def __init__(self):
        super().__init__()

        self.next_fields : list = [
                ['nova_inode_page_tail.next_page'],
            ]

    def next_fields(self) -> list:
        return [
            ['nova_inode_page_tail.next_page'],
        ]


class CheatSheetNova(CheatSheetBase):
    def __init__(self):
        super().__init__()
        self.filesystem : str = 'nova'
        self.undo_jnl_sheet : UndoJnlCheatSheetBase = UndoJnlCheatSheet()
        self.lsw_sheet_list : list = [LSWCheatSheet1(), LSWCheatSheet2()]
        self.rep_sheet : RepCheatSheetBase = RepCheatSheet()
        self.link_sheet : LinkedListCheatSheetBase = None
