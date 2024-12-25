#!/bin/bash
set -e
set -x

FS_TYPE="nova"
CP_TYPE="mech2cp"
# validate crash plans for the mech2cp crash plan generation scheme.
DO_NOT_VALIDATE="false"
NUM_VMS="20"

BASE_ENV_FILE="../../../../../codebase/scripts/fs_conf/base/env_base.py"
HOST_SCRIPT="../../../../../codebase/scripts/executor/host_side/main_host.py"

current_dir=$(pwd)
analysis_dir="../../../../../codebase/scripts/executor/host_side/result_analysis"

RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Clean up for testing
bash ../../../../cleanup_for_testing.sh
sleep 5

# 2. Patch the EXEC_FILES method in env_base.py.
PATCH_CODE="
def exec_files_path(self) -> list:
    return ['/home/bing/seq2_11func_bin']

EnvBase.EXEC_FILES = exec_files_path
"

START_LINE=$(wc -l < "$BASE_ENV_FILE")
START_LINE=$((START_LINE + 1))
echo "$PATCH_CODE" >> "$BASE_ENV_FILE"
END_LINE=$(wc -l < "$BASE_ENV_FILE")

# 3. Start memcached
memcached -d -m 4096 -t 4 -R 10 -p 11211  -l 127.0.0.1 -c 1024 -I 512m -P /var/run/memcached/memcached.pid -o no_maxconns_fast

# 4. Run Silhouette.
nohup python3 "$HOST_SCRIPT" \
    --fs_type "$FS_TYPE" \
    --num_vms "$NUM_VMS" \
    --crash_plan_scheme "$CP_TYPE" \
    --stop_after_gen_crash_plan "$DO_NOT_VALIDATE" \
    --clean_up_vm true \
    --time_logger_local_file ./log.time.host \
    --time_logger_server_file ./log.time.remote \
    --logging_file ./log.main \
    --logging_level 30 &

PID=$!
wait $PID

# 5. Remove patch
sed -i "${START_LINE},${END_LINE}d" "$BASE_ENV_FILE"

# 6. Analyze the result
cd "$analysis_dir"
./dump_all.sh "$current_dir/result" "$current_dir/log.time.*"
cd "$current_dir"

# 7. Clean up for the next testing
bash ../../../../cleanup_for_testing.sh
