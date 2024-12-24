"""The resource if system"""
import resource

class ResourceRecord:
    """ResourceRecord."""
    def __init__(self, name="NoName"):
        self.name = name

        # resource records [self_record, child_record], either one could be None
        # generally, the list only contain 2 records, that we can calculate the 
        # elapsed time and resource used.
        # If only one record, we will report error.
        # If more than two records, we calculate the elapse between the first and last
        self.resrc_list = []

    @classmethod
    def rusage_diff_str(cls, usage_start, usage_end):
        if usage_start == None or usage_end == None:
            return ""
        
        data = ""

        data += 'ru_utime:'    + str(usage_end.ru_utime - usage_start.ru_utime) + "\n"
        data += 'ru_stime:'    + str(usage_end.ru_stime - usage_start.ru_stime) + "\n"
        data += 'ru_maxrss:'   + str(usage_end.ru_maxrss - usage_start.ru_maxrss) + "\n"
        data += 'ru_ixrss:'    + str(usage_end.ru_ixrss - usage_start.ru_ixrss) + "\n"
        data += 'ru_idrss:'    + str(usage_end.ru_idrss - usage_start.ru_idrss) + "\n"
        data += 'ru_isrss:'    + str(usage_end.ru_isrss - usage_start.ru_isrss) + "\n"
        data += 'ru_minflt:'   + str(usage_end.ru_minflt - usage_start.ru_minflt) + "\n"
        data += 'ru_majflt:'   + str(usage_end.ru_majflt - usage_start.ru_majflt) + "\n"
        data += 'ru_nswap:'    + str(usage_end.ru_nswap - usage_start.ru_nswap) + "\n"
        data += 'ru_inblock:'  + str(usage_end.ru_inblock - usage_start.ru_inblock) + "\n"
        data += 'ru_oublock:'  + str(usage_end.ru_oublock - usage_start.ru_oublock) + "\n"
        data += 'ru_msgsnd:'   + str(usage_end.ru_msgsnd - usage_start.ru_msgsnd) + "\n"
        data += 'ru_msgrcv:'   + str(usage_end.ru_msgrcv - usage_start.ru_msgrcv) + "\n"
        data += 'ru_nsignals:' + str(usage_end.ru_nsignals - usage_start.ru_nsignals) + "\n"
        data += 'ru_nvcsw:'    + str(usage_end.ru_nvcsw - usage_start.ru_nvcsw) + "\n"
        data += 'ru_nivcsw:'   + str(usage_end.ru_nivcsw - usage_start.ru_nivcsw)

        return data
    
    @classmethod
    def rusage_str(cls, usage):
        if usage == None:
            return ""
        
        data = ""

        data += 'ru_utime:'    + str(usage.ru_utime) + "\n"
        data += 'ru_stime:'    + str(usage.ru_stime) + "\n"
        data += 'ru_maxrss:'   + str(usage.ru_maxrss) + "\n"
        data += 'ru_ixrss:'    + str(usage.ru_ixrss) + "\n"
        data += 'ru_idrss:'    + str(usage.ru_idrss) + "\n"
        data += 'ru_isrss:'    + str(usage.ru_isrss) + "\n"
        data += 'ru_minflt:'   + str(usage.ru_minflt) + "\n"
        data += 'ru_majflt:'   + str(usage.ru_majflt) + "\n"
        data += 'ru_nswap:'    + str(usage.ru_nswap) + "\n"
        data += 'ru_inblock:'  + str(usage.ru_inblock) + "\n"
        data += 'ru_oublock:'  + str(usage.ru_oublock) + "\n"
        data += 'ru_msgsnd:'   + str(usage.ru_msgsnd) + "\n"
        data += 'ru_msgrcv:'   + str(usage.ru_msgrcv) + "\n"
        data += 'ru_nsignals:' + str(usage.ru_nsignals) + "\n"
        data += 'ru_nvcsw:'    + str(usage.ru_nvcsw) + "\n"
        data += 'ru_nivcsw:'   + str(usage.ru_nivcsw)

        return data

    def diff_self_str(self):
        self_list = [x[0] for x in self.resrc_list if x[0] != None]
        if len(self_list) < 1:
            return ""        
        return self.rusage_diff_str(self_list[0], self_list[-1])

    def diff_child_str(self):
        child_list = [x[1] for x in self.resrc_list if x[1] != None]
        if len(child_list) < 1:
            return ""        
        return self.rusage_diff_str(child_list[0], child_list[-1])

    def record(self, record_self=True, record_child=False):
        record = [None, None]
        if record_self:
            record[0] = resource.getrusage(resource.RUSAGE_SELF)
        if record_child:
            record[1] = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.resrc_list.append(record)
            
    def clear(self):
        self.resrc_list.clear()