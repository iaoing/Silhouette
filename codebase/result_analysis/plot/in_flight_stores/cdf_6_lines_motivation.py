import sys
import itertools
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

'''
Plot the CDF of in-flight stores at ordering points.
This version plots 3 lines for one given file system:
1. PMFS - Silhouette
2. PMFS - Chipmunk
3. PMFS - Vinter
OR
1. NOVA - Silhouette
2. NOVA - Chipmunk
3. NOVA - Vinter
OR
1. WineFS - Silhouette
2. WineFS - Chipmunk
3. WineFS - Vinter
'''

def calculate_cdf(data):
    sorted_data = np.sort(data)
    # min_value = sorted_data[0]
    # normalized_data = sorted_data - min_value
    # cdf = np.arange(1, len(normalized_data) + 1) / len(normalized_data)
    cdf = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
    return sorted_data, cdf

def load_data(file_list):
    sorted_data_list = []
    cdf_list = []
    for fname in file_list:
        data = np.loadtxt(fname)
        # data = data[data != 0]
        sorted_data, cdf = calculate_cdf(data)
        sorted_data_list.append(sorted_data)
        cdf_list.append(cdf)

    return sorted_data_list, cdf_list

def plot(sorted_data_list, cdf_list, label_list, x_title, save_fname):
    # Create a CDF plot
    plt.figure(figsize=(7, 4))
    # marker = itertools.cycle(('x', 'o', 's'))
    marker = itertools.cycle(('x', 'o', '^'))
    # color_list = ['k', 'k', 'k']
    # color_list = ['b', 'g', 'r', 'b', 'g', 'r']
    color_list = ['b', '#ff7f0e', 'g', 'b', '#ff7f0e', 'g']

    for i in range(len(sorted_data_list)):
        sorted_data = sorted_data_list[i]
        cdf = cdf_list[i]
        label = label_list[i]
        marker_list = [False for x in cdf]
        last_x_asix_num = -1

        # custom list for markevery
        # for j in range(len(marker_list)):
        #     if int(sorted_data[j]) != last_x_asix_num:
        #         if int(sorted_data[j]) % 2 == 0:
        #             marker_list[j] = True
        #         last_x_asix_num = int(sorted_data[j])

        # sanitize data for a smooth curve
        def find_last_index(lst, element):
            return len(lst) - 1 - lst[::-1].index(element)
        # print(sorted_data)
        # print(cdf)
        sorted_data = sorted_data.tolist()
        cdf = cdf.tolist()
        sanitized_data = [x for x in range(0, int(max(sorted_data))+1)]
        sanitized_cdf = [0 for x in sanitized_data]
        for j in sanitized_data:
            if j not in sorted_data:
                if j == 0:
                    sanitized_cdf[j] = 0
                else:
                    sanitized_cdf[j] = sanitized_cdf[j-1]
            else:
                idx = find_last_index(sorted_data, j)
                sanitized_cdf[j] = cdf[idx]
        print(sanitized_data)
        print(sanitized_cdf)


        if i < 3:
            plt.plot(sanitized_data, sanitized_cdf, color=color_list[i],
                     markevery=1, marker=next(marker), markerfacecolor='none', markersize=5, linewidth=1,
                     linestyle='-', label=label, alpha=1)
        else:
            plt.plot(sanitized_data, sanitized_cdf, color=color_list[i],
                     markevery=1, marker=next(marker), markerfacecolor='none', markersize=5, linewidth=1,
                     linestyle=':', label=label, alpha=1)


    # plt.xscale('log')
    plt.xlabel(x_title, fontsize=20)
    plt.xlim([0, 40])

    plt.ylabel('CDF', fontsize=20)
    plt.ylim([0, 1])

    ax = plt.gca()

    # ax.xaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=5))
    # ax.xaxis.set_minor_locator(ticker.LogLocator(base=10.0, subs=(0.2, 0.4, 0.6, 0.8), numticks=5))
    # ax.xaxis.set_minor_formatter(ticker.FormatStrFormatter("%d"))
    # ax.xaxis.set_tick_params(which='minor', labelsize=12)
    ax.xaxis.set_tick_params(which='major', labelsize=20)
    ax.yaxis.set_tick_params(which='major', labelsize=20)

    # major_ticks = [10, 100]
    # minor_ticks = list(range(0, 100, 20))
    # print(minor_ticks)
    # plt.xticks(major_ticks)
    # plt.xticks(minor_ticks, minor=True)
    plt.grid(which='major', axis='x', ls='--', alpha=0.9)
    plt.grid(which='minor', axis='x', ls='--', alpha=0.3)
    plt.grid(axis='y', ls='--', alpha=0.9)

    # plt.title('Cumulative Distribution Function (CDF) Plot')
    plt.legend(loc='lower right', markerscale=1.1, prop={'size': 16})

    plt.tight_layout()
    # plt.show()
    plt.savefig(save_fname)

def main():
    file_list = [sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]]
    save_fname = sys.argv[7]

    label_list = ['NOVA - in-flight stores', 'PMFS - in-flight stores', 'WineFS - in-flight stores',
                  'NOVA - unprotected stores', 'PMFS - unprotected stores', 'WineFS - unprotected stores']
    sorted_data_list, cdf_list = load_data(file_list)
    plot(sorted_data_list, cdf_list, label_list, '# of in-flight stores at ordering points', save_fname)


if __name__ == "__main__":
    main()

