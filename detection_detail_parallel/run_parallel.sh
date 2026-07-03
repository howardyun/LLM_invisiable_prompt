#!/usr/bin/env bash
set -e

if [ "$#" -lt 1 ]; then
  echo "Usage: bash detection_detail_parallel/run_parallel.sh <pdf_path> [output_dir] [max_pages] [extra args...]"
  exit 2
fi

PDF_PATH="$1"
OUT_DIR="${2:-detection_detail_parallel/out}"
MAX_PAGES="${3:-}"

shift
if [ "$#" -gt 0 ]; then shift; fi
if [ "$#" -gt 0 ]; then shift; fi

ARGS=(
  --pdf "$PDF_PATH"
  --out "$OUT_DIR"
)

if [ -n "$MAX_PAGES" ] && [ "$MAX_PAGES" != "0" ]; then
  ARGS+=(--max-pages "$MAX_PAGES")
fi

START_TIME="$(date +%s)"

set +e
python detection_detail_parallel/scan_pdf_parallel.py "${ARGS[@]}" "$@"
EXIT_CODE=$?
set -e

END_TIME="$(date +%s)"
ELAPSED_SECONDS=$((END_TIME - START_TIME))
echo "Detection elapsed seconds: $ELAPSED_SECONDS"

mkdir -p "$OUT_DIR"
echo "$(date '+%Y-%m-%d %H:%M:%S') pdf=$PDF_PATH exit_code=$EXIT_CODE elapsed_seconds=$ELAPSED_SECONDS" >> "$OUT_DIR/run_parallel_timing.log"

exit "$EXIT_CODE"