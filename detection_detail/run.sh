#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PDF_PATH="${1:?Usage: bash run.sh <pdf_path> [output_dir] [max_pages]}"
OUTPUT_DIR="${2:-$SCRIPT_DIR/outputs}"
MAX_PAGES="${3:-}"

if [[ -x "$PROJECT_ROOT/venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
elif [[ -x "$PROJECT_ROOT/venv/Scripts/python.exe" ]]; then
  PYTHON_BIN="$PROJECT_ROOT/venv/Scripts/python.exe"
else
  PYTHON_BIN="${PYTHON_BIN:-python}"
fi

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

ARGS=(
  --pdf "$PDF_PATH"
  --out "$OUTPUT_DIR"
  --device cuda
  --dpi 180
  --draw-bboxes
)

if [[ -n "$MAX_PAGES" ]]; then
  ARGS+=(--max-pages "$MAX_PAGES")
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/scan_pdf.py" "${ARGS[@]}"
