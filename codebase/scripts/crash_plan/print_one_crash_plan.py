import os
import sys
import pickle

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from logic_reason.crash_plan.crash_plan_entry import CrashPlanEntry, CrashPlanType, CrashPlanSamplingType


def main():
    if len(sys.argv) != 2:
        print("invalid usage")
        exit(0)
    
    fname = sys.argv[1]
    with open(fname, 'rb') as fd:
        entry = pickle.load(fd)
        print(entry)

if __name__ == "__main__":
    main()
