#!/bin/bash

RED='\033[0;31m'
NC='\033[0m' # No Color

analyze_py="../../../codebase/result_analysis/silhouette/scripts/in_flight_store_analysis/analyze.py"
figure1_py="../../../codebase/result_analysis/plot/in_flight_stores/cdf_6_lines_motivation.py"

# Analyze the result to get the number of unprotected stores and in-flight stores
python3 "$analyze_py" ./nova/2cp/result
python3 "$analyze_py" ./nova/mech2cp/result
python3 "$analyze_py" ./nova/mechcomb/result

python3 "$analyze_py" ./pmfs/2cp/result
python3 "$analyze_py" ./pmfs/mech2cp/result
python3 "$analyze_py" ./pmfs/mechcomb/result

python3 "$analyze_py" ./winefs/2cp/result
python3 "$analyze_py" ./winefs/mech2cp/result
python3 "$analyze_py" ./winefs/mechcomb/result

# Plot Figure 1
python3 "$figure1_py" \
    ./nova/mech2cp/result/res.in.flight.stores.txt \
    ./pmfs/mech2cp/result/res.in.flight.stores.txt \
    ./winefs/mech2cp/result/res.in.flight.stores.txt \
    ./nova/mech2cp/result/res.in.flight.unprotected.stores.txt \
    ./pmfs/mech2cp/result/res.in.flight.unprotected.stores.txt \
    ./winefs/mech2cp/result/res.in.flight.unprotected.stores.txt \
    ./figure_1.pdf

# Get Table 3
cps_nova_mech2cp=$(awk '{s+=$NF} END {print s}' ./nova/mech2cp/result/result_cps/result.txt)
cps_pmfs_mech2cp=$(awk '{s+=$NF} END {print s}' ./pmfs/mech2cp/result/result_cps/result.txt)
cps_winefs_mech2cp=$(awk '{s+=$NF} END {print s}' ./winefs/mech2cp/result/result_cps/result.txt)

cps_nova_2cp=$(awk '{s+=$NF} END {print s}' ./nova/2cp/result/result_cps/result.txt)
cps_pmfs_2cp=$(awk '{s+=$NF} END {print s}' ./pmfs/2cp/result/result_cps/result.txt)
cps_winefs_2cp=$(awk '{s+=$NF} END {print s}' ./winefs/2cp/result/result_cps/result.txt)

cps_nova_mechcomb=$(awk '{s+=$NF} END {print s}' ./nova/mechcomb/result/result_cps/result.txt)
cps_pmfs_mechcomb=$(awk '{s+=$NF} END {print s}' ./pmfs/mechcomb/result/result_cps/result.txt)
cps_winefs_mechcomb=$(awk '{s+=$NF} END {print s}' ./winefs/mechcomb/result/result_cps/result.txt)

echo -e "              \tNOVA\tPMFS\tWineFS" > ./table_3.txt
echo -e "Silhouette    \t$cps_pmfs_mech2cp\t$cps_pmfs_mech2cp\t$cps_winefs_mech2cp"  >> ./table_3.txt
echo -e "2CP           \t$cps_nova_2cp\t$cps_pmfs_2cp\t$cps_winefs_2cp"  >> ./table_3.txt
echo -e "Invariant+Comb\t$cps_nova_mechcomb\t$cps_pmfs_mechcomb\t$cps_winefs_mechcomb"  >> ./table_3.txt

echo -e "Generated Figure 1: ${RED}figure_1.pdf${NC} (the blue line in Figure 9 is the same as in Figure 1)"
echo -e "Generated Table 3: ${RED}table_3.txt${NC}"
