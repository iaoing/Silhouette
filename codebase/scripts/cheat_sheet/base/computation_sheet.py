import os
import sys

scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(scripts_dir)

import scripts.utils.logger as log

class ComputationElement:
    def __init__(self, st_name, var_name, signed, value) -> None:
        self.st_name = st_name
        self.var_name = var_name
        self.signed = signed
        self.value : int = value
        self.aux = None # for extra information felid

    def __str__(self):
        return f'{self.st_name}.{self.var_name}.{"signed" if self.signed else "unsigned"}({self.value})'

    def __repr__(self) -> str:
        return self.__str__()

class ComputationSheet:
    '''
    The structure and variable based computation.
    Use Reverse Polish notation (RPN) to represent the computation.
    Only support + - * / of signed/unsigned integers..
    For example, the input rpn_list should be ['journal.base.unsigned', 'journal.head.unsigned', '+'] for journal.base + journal.head = head_pm_address, in which the 'unsigned' mark indicates this variable is an unsigned value
    '''
    def __init__(self, rpn_list) -> None:
        ''' We do not check whether the rpn is valid. '''
        # if no computations are required (e.g.,only one element), the structure name
        # and variable name of the result address in the list
        assert rpn_list, "RPN cannot be none"

        self.rpn = []
        self.is_pure_number = True
        self.pure_num = None
        # for fast checks of the structure-variable existence
        self.st_set = set()
        for e in rpn_list:
            if e in ['+', '-', '*', '/']:
                self.rpn.append(e)
            elif isinstance(e, int) or e.isnumeric():
                self.rpn.append(ComputationElement(None, None, None, int(e)))
                self.pure_num = int(e)
            elif e.count('.') == 2:
                self.is_pure_number = False
                st_name = e.split(".")[0]
                var_name = e.split(".")[1]
                signed = True if e.split(".")[2] == "signed" else False
                self.rpn.append(ComputationElement(st_name, var_name, signed, None))
                self.st_set.add(f'{st_name}.{var_name}')
            else:
                msg = "invalid computation elements %s" % (e)
                log.global_logger.critical(msg)
                assert False, msg

    def get_operands(self) -> list:
        '''Only return structure-based computation elements'''
        return [x for x in self.rpn if isinstance(x, ComputationElement) and x.st_name and x.var_name]

    def contain_var(self, st_name, var_name) -> bool:
        return f'{st_name}.{var_name}' in self.st_set

    def get_value(self, st_name, var_name):
        if not self.contain_var(st_name, var_name):
            return None
        for e in self.rpn:
            if isinstance(e, ComputationElement) and \
                    e.st_name == st_name and e.var_name == var_name:
                return e.value
        return None

    def set_value(self, st_name, var_name, val, convert_from_bytes) -> bool:
        '''return true if struct and var names are matched'''
        if self.is_pure_number:
            return True

        if not self.contain_var(st_name, var_name):
            # if log.debug:
            #     msg = f"not in computation elements: {st_name}.{var_name} not in {self.st_set}"
            #     log.global_logger.debug(msg)
            return False
        ret = False
        for e in self.rpn:
            # if log.debug:
            #     msg = f"in computation elements: {st_name}.{var_name} in {self.st_set}"
            #     log.global_logger.debug(msg)
            if isinstance(e, ComputationElement) and \
                    e.st_name == st_name and e.var_name == var_name:
                if convert_from_bytes:
                    e.value = int.from_bytes(val, byteorder='little', signed=e.signed)
                else:
                    e.value = val
                ret = True
        return ret

    def clean_val(self):
        if self.is_pure_number:
            return

        for e in self.rpn:
            if isinstance(e, ComputationElement):
                e.value = None

    def is_finalized(self) -> bool:
        if self.is_pure_number:
            return True

        for e in self.rpn:
            if isinstance(e, ComputationElement):
                if e.value == None:
                    return False
        return True

    def evaluate(self):
        if self.is_pure_number:
            return self.pure_num

        stack = []
        for e in self.rpn:
            if isinstance(e, ComputationElement):
                stack.append(e.value)
            else:
                operand1 = stack.pop()
                operand2 = stack.pop()

                if e == '+':
                    result = operand2 + operand1
                elif e == '-':
                    result = operand2 - operand1
                elif e == '*':
                    result = operand2 * operand1
                elif e == '/':
                    result = operand2 / operand1

                stack.append(result)
        return stack[0]

    def dbg_str(self):
        buf = ""
        for e in self.rpn:
            buf += str(e) + " "
        return buf

    def __str__(self):
        return self.dbg_str()

    def __repr__(self) -> str:
        return self.__str__()
