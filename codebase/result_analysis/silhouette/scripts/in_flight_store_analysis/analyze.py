import sys
import os
import glob
import ast
from tqdm import tqdm
from collections import Counter

'''
In the old version of Silhouette, the log of 2CP scheme does not contain the
number of in-flight unprotected stores at ordering points, it only has the
total number of unprotected stores for a VFS operation.
Since the Mech + Comb scheme has information of in-flight unprotected stores
at ordering points, we use it to extract the number.
'''
def analyze_one_log_file(log_file : str):
    unprotected_store_list = []
    in_flight_store_list = []

    if not os.path.exists(log_file):
        return [], []

    fd = open(log_file, 'r')
    lines = fd.readlines()
    fd.close()

    # print(log_file)

    fence_dict = dict()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('CrashPlanType'):
            break

        # print(line)
        if line.startswith('seq,fence_seq,addr,size,struct,var,src'):
            # this is a bug due to no newline at the first output
            line = line[len('seq,fence_seq,addr,size,struct,var,src'):]

        if line.startswith('flush:'):
            pass
        elif line.startswith('fence:'):
            items = line.split(':')
            fence_seq = int(items[1])

            if fence_seq not in fence_dict:
                continue
            else:
                num_stores = 0
                num_unprotected_stores = 0
                for seq, stores in fence_dict.items():
                    num_stores += len(stores)
                    num_unprotected_stores += len([x for x in stores if x[1] == 2])

                in_flight_store_list.append(num_stores)
                unprotected_store_list.append(num_unprotected_stores)

                del fence_dict[fence_seq]

        elif line.count(',') >= 6:
            items = line.split(',')
            if items[0].isnumeric() and items[1].isnumeric():
                update_seq = int(items[0])
                fence_seq = int(items[1])

                if fence_seq not in fence_dict:
                    fence_dict[fence_seq] = []

                if 'lsw' in items[-1] or 'rep' in items[-1] or 'jnl' in items[-1]:
                    # mech-protected stores
                    fence_dict[fence_seq].append([update_seq, 1])
                else:
                    # unprotected stores
                    fence_dict[fence_seq].append([update_seq, 2])

    for fence_seq, stores in fence_dict.items():
        num_stores = 0
        num_unprotected_stores = 0
        for seq, stores in fence_dict.items():
            num_stores += len(stores)
            num_unprotected_stores += len([x for x in stores if x[1] == 2])

        in_flight_store_list.append(num_stores)
        unprotected_store_list.append(num_unprotected_stores)

    return unprotected_store_list, in_flight_store_list

def analyze(res_dir : str):
    log_dir = res_dir + '/result_details'
    num_unprotected_store_without_sampling_at_fence_point = []
    num_in_flight_store_without_sampling_at_fence_point = []

    for fname in tqdm(glob.glob(log_dir + '/*.txt')):
        unprotected_store_list, in_flight_store_list = analyze_one_log_file(fname)
        if len(unprotected_store_list) == 0 and in_flight_store_list == 0:
            continue
        else:
            num_unprotected_store_without_sampling_at_fence_point += unprotected_store_list
            num_in_flight_store_without_sampling_at_fence_point += in_flight_store_list

    res_output_fpath = res_dir + '/res.in.flight.unprotected.stores.txt'
    res_str = '#### number of in-flight unprotected stores at ordering points, considering the non-atomic write as a single write\n'
    res_str += f'## number of ordering points: {len(num_unprotected_store_without_sampling_at_fence_point)}\n'
    res_str += f'## distribution: {str(Counter(num_unprotected_store_without_sampling_at_fence_point))}\n'
    print(res_str)
    for num in num_unprotected_store_without_sampling_at_fence_point:
        res_str += f'{num}\n'
    with open(res_output_fpath, 'w') as fd:
        fd.write(res_str)

    res_output_fpath = res_dir + '/res.in.flight.stores.txt'
    res_str = '#### number of in-flight stores at ordering points, considering the non-atomic write as a single write\n'
    res_str += f'## number of ordering points: {len(num_in_flight_store_without_sampling_at_fence_point)}\n'
    res_str += f'## distribution: {str(Counter(num_in_flight_store_without_sampling_at_fence_point))}\n'
    print(res_str)
    for num in num_in_flight_store_without_sampling_at_fence_point:
        res_str += f'{num}\n'
    with open(res_output_fpath, 'w') as fd:
        fd.write(res_str)

def main():
    if len(sys.argv) != 2:
        print("invalid arguments")
        exit(0)

    res_dir = sys.argv[1]
    analyze(res_dir)


if __name__ == "__main__":
    main()