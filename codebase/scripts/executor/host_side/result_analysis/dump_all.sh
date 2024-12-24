#!/bin/bash

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Error: You must provide arguments."
  echo "Usage: ./script.sh <output_dir> <input_time_log>"
  exit 1  # Exit the script with an error code
fi

OUTPUT_DIR=$1
TIME_LOG=$2

python3 ./dump_cache_sim_result.py -o "$OUTPUT_DIR/result_cache_sim"
python3 ./dump_crash_plan_count_result.py -o "$OUTPUT_DIR/result_cps"
python3 ./dump_elapsed_time.py -o "$OUTPUT_DIR/result_elapsed_time" -i "$TIME_LOG"
python3 ./dump_failed_test_cases.py -o "$OUTPUT_DIR/result_failed_test_cases"
python3 ./dump_invariant_check_result_from_memcached.py -o "$OUTPUT_DIR/result_invaraints"
python3 ./dump_tracing_result_from_memcached.py -o "$OUTPUT_DIR/result_tracing"
python3 ./dump_unique_ops.py -o "$OUTPUT_DIR/result_unique_ops"
python3 ./dump_validation_result_from_memcached.py -o "$OUTPUT_DIR/result_validation"
python3 ./dump_crash_plan_to_validate_result.py -o "$OUTPUT_DIR/result_cps2validation"

# for debugging
python3 ./dump_detailed_info.py -o "$OUTPUT_DIR/result_details"

# dump vm info
python3 ../print_memcached_info.py >> "$OUTPUT_DIR/result_vminfo.txt"

# dump memcached status and stats
mkdir -p "$OUTPUT_DIR/result_memcached_info"
sudo systemctl status memcached >> "$OUTPUT_DIR/result_memcached_info/memcached_status.txt"
echo "stats" | nc -w 1 127.0.0.1 11211 >> "$OUTPUT_DIR/result_memcached_info/memcached_stats.txt"
