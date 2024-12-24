#!/bin/bash
set -e
set -x

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# 1. Patch the EXEC_FILES method in env_base.py.
BASE_ENV_FILE="../../../codebase/scripts/fs_conf/base/env_base.py"
BASE_ENV_PATCH_CODE="
def exec_files_path(self) -> list:
    return ['/home/bing/seq1_11func_bin']

EnvBase.EXEC_FILES = exec_files_path
"

BASE_ENV_START_LINE=$(wc -l < "$BASE_ENV_FILE")
BASE_ENV_START_LINE=$((BASE_ENV_START_LINE + 1))
echo "$BASE_ENV_PATCH_CODE" >> "$BASE_ENV_FILE"
BASE_ENV_END_LINE=$(wc -l < "$BASE_ENV_FILE")

# 2. Patch the MOD_INS_PARA in env_nova.py
bash ./enable_bug.sh
NOVA_ENV_FILE="../../../codebase/scripts/fs_conf/nova/env_nova.py"
NOVA_ENV_PATCH_CODE="
def mod_ins_para_path(self) -> list:
    return 'metadata_csum=1 data_csum=1 data_parity=1 dram_struct_csum=1'

EnvNova.MOD_INS_PARA = mod_ins_para_path
"

NOVA_ENV_START_LINE=$(wc -l < "$NOVA_ENV_FILE")
NOVA_ENV_START_LINE=$((NOVA_ENV_START_LINE + 1))
echo "$NOVA_ENV_PATCH_CODE" >> "$NOVA_ENV_FILE"
NOVA_ENV_END_LINE=$(wc -l < "$NOVA_ENV_FILE")

# 3. Start memcached
memcached -d -m 4096 -t 4 -R 10 -p 11211 -u memcache -l 127.0.0.1 -c 1024 -I 512m -P /var/run/memcached/memcached.pid -o no_maxconns_fast

# 4. Run Silhouette
HOST_SCRIPT="../../../codebase/scripts/executor/host_side/main_host.py"
TEST_CASE="j-lang1"
nohup python3 "$HOST_SCRIPT" \
    --fs_type nova \
    --num_vms 1 \
    --crash_plan_scheme mech2cp \
    --test_case_basename "$TEST_CASE" \
    --clean_up_vm true \
    --time_logger_local_file ./log.time.host \
    --time_logger_server_file ./log.time.remote \
    --logging_file ./log.main \
    --logging_level 30 &

PID=$!
wait $PID

# 5. Remove patch
bash ./disable_bug.sh
sed -i "${BASE_ENV_START_LINE},${BASE_ENV_END_LINE}d" "$BASE_ENV_FILE"
sed -i "${NOVA_ENV_START_LINE},${NOVA_ENV_END_LINE}d" "$NOVA_ENV_FILE"

# 6. Analyze the result
current_dir=$(pwd)
analysis_dir="../../../codebase/scripts/executor/host_side/result_analysis"
cd "$analysis_dir"
./dump_all.sh "$current_dir/result" "$current_dir/log.time.*"
cd "$current_dir"

echo -e "Please refer to ${RED}readme.md${NC} to check the result."
