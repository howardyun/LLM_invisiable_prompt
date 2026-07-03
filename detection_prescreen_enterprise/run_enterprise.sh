#!/usr/bin/env bash
set -e

if [ "$#" -lt 1 ]; then
  echo "Usage: bash detection_prescreen_enterprise/run_enterprise.sh <input_dir> [output_dir] [extra args...]"
  exit 2
fi

INPUT_DIR="$1"
OUT_DIR="${2:-detection_prescreen_enterprise/out}"

shift
if [ "$#" -gt 0 ]; then shift; fi

START_TIME="$(date +%s)"

set +e
python detection_prescreen_enterprise/enterprise_batch.py --input-dir "$INPUT_DIR" --out "$OUT_DIR" "$@"
EXIT_CODE=$?
set -e

END_TIME="$(date +%s)"
ELAPSED_SECONDS=$((END_TIME - START_TIME))
echo "Enterprise prescreen elapsed seconds: $ELAPSED_SECONDS"

mkdir -p "$OUT_DIR"
echo "$(date '+%Y-%m-%d %H:%M:%S') input_dir=$INPUT_DIR exit_code=$EXIT_CODE elapsed_seconds=$ELAPSED_SECONDS" >> "$OUT_DIR/run_enterprise_timing.log"

exit "$EXIT_CODE"
