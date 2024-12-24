import os
import sys
import pickle

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(base_dir)

from logic_reason.crash_plan.crash_plan_pm_data import CrashPlanPMData


def main():
    if len(sys.argv) != 2:
        print("invalid usage")
        exit(0)
    
    fname = sys.argv[1]
    with open(fname, 'rb') as fd:
        entry = pickle.load(fd)
        print(entry.dbg_detail_str(100))

if __name__ == "__main__":
    main()
