#!/bin/bash
set -e
set -x

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# 1. Patch the EXEC_FILES method in env_base.py.
BASE_ENV_FILE="../../../codebase/scripts/fs_conf/base/env_base.py"
PATCH_CODE="
def exec_files_path(self) -> list:
    return ['/home/bing/seq2_11func_bin']

EnvBase.EXEC_FILES = exec_files_path
"

START_LINE=$(wc -l < "$BASE_ENV_FILE")
START_LINE=$((START_LINE + 1))
echo "$PATCH_CODE" >> "$BASE_ENV_FILE"
END_LINE=$(wc -l < "$BASE_ENV_FILE")

# 2. Start memcached
memcached -d -m 4096 -t 4 -R 10 -p 11211 -u memcache -l 127.0.0.1 -c 1024 -I 512m -P /var/run/memcached/memcached.pid -o no_maxconns_fast

# 3. Run Silhouette
HOST_SCRIPT="../../../codebase/scripts/executor/host_side/main_host.py"
TEST_CASE="j-lang2787"
nohup python3 "$HOST_SCRIPT" \
    --fs_type nova \
    --num_vms 1 \
    --crash_plan_scheme mech2cp \
    --test_case_basename "$TEST_CASE" \
    --not_dedup 1 \
    --clean_up_vm true \
    --time_logger_local_file ./log.time.host \
    --time_logger_server_file ./log.time.remote \
    --logging_file ./log.main \
    --logging_level 30 &

PID=$!
wait $PID

# 4. Remove patch
sed -i "${START_LINE},${END_LINE}d" "$BASE_ENV_FILE"

# 5. Analyze the result
current_dir=$(pwd)
analysis_dir="../../../codebase/scripts/executor/host_side/result_analysis"
cd "$analysis_dir"
./dump_all.sh "$current_dir/result" "$current_dir/log.time.*"
cd "$current_dir"

echo -e "Please refer to ${RED}readme.md${NC} to check the result."