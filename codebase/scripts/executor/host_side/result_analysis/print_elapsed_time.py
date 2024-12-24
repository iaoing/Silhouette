import os
import sys
import glob
from collections import Counter
from prettytable import PrettyTable

def print_int_list_distribution(ll : list):
    print(str(Counter(ll)))

def print_elapsed_time_dict_as_table(elapsed_time_map):
    # Create a PrettyTable object
    table = PrettyTable()

    # Add columns to the table
    table.field_names = ["Function Name", "# of Calls", "Sum (seconds)", "Avg (seconds)"]

    for key, value in elapsed_time_map.items():
        table.add_row([key, len(value), f'{sum(value):,.6f}', f'{sum(value)/len(value):,.6f}'])

    table.align["Function Name"] = "l"
    table.align["# of Calls"] = "r"
    table.align["Sum (seconds)"] = "r"
    table.align["Avg (seconds)"] = "r"

    # Print the table
    print(table)

def get_elapsed_time_title(line : str) -> str:
    title = line[line.find('elapsed_time'):]
    title = title.split(':')[0]
    title = title[len('elapsed_time.'):]
    return title

def get_elapsed_time_time(line : str) -> float:
    time = float(line.split(':')[-1])
    return time

def brief_time_in_one_file(fpath, elapsed_time_map) -> dict:
    print(f"read {fpath}")
    with open(fpath, 'r') as fd:
        for line in fd:
            line = line.strip()
            if 'elapsed_time.' in line:
                title = get_elapsed_time_title(line)
                time = get_elapsed_time_time(line)
                if title not in elapsed_time_map:
                    elapsed_time_map[title] = []
                elapsed_time_map[title].append(time)
    return elapsed_time_map

def main():
    if len(sys.argv) == 1:
        print("Invalid arguments.")
        print("The argument could be the path to a file, a path to a directory, or a regex path supportted by glob.")
        exit(1)

    elapsed_time_map = dict()
    for path in sys.argv[1:]:
        if os.path.isfile(path):
            elapsed_time_map = brief_time_in_one_file(path, elapsed_time_map)
        elif os.path.isdir(path):
            for fpath in glob.glob(path + "/*"):
                if os.path.isfile(fpath):
                    elapsed_time_map = brief_time_in_one_file(fpath, elapsed_time_map)
        else:
            for fpath in glob.glob(path):
                if os.path.isfile(fpath):
                    elapsed_time_map = brief_time_in_one_file(fpath, elapsed_time_map)

    print_elapsed_time_dict_as_table(elapsed_time_map)

if __name__ == "__main__":
    main()
