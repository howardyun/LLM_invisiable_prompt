# detection_detail_parallel

Patch-level detector wrapper for the existing `detection_detail` pipeline.

The original detector folder is left untouched.  This folder reuses the same
layout extraction, matching rules, thresholds, JSON writers, and CSV fields,
but the default OCR path is now a single RapidOCR Torch model with batched
classifier/recognizer inference.  The older Docling worker-pool OCR path is
still available with `--ocr-mode workers` for comparison.

## Single PDF

```powershell
python .\detection_detail_parallel\scan_pdf_parallel.py `
  --pdf .\Data\PDF\DGA_IWQOS2025.pdf `
  --out .\detection_detail_parallel\out `
  --device cuda `
  --max-pages 3 `
  --no-draw-bboxes
```

The bash wrapper is intentionally thin and records elapsed seconds:

```bash
bash detection_detail_parallel/run_parallel.sh Data/PDF/DGA_IWQOS2025.pdf detection_detail_parallel/out 3 --device cuda --no-draw-bboxes
```

## OCR Modes

- `--ocr-mode batch` (default): one RapidOCR model instance, batched text-line
  classification and recognition for primary patches and second-pass gap crops.
- `--ocr-mode workers`: the previous Docling worker-pool OCR mode. Useful only
  for A/B testing because multiple CUDA OCR workers can compete for the same GPU.

Batch tuning knobs:

- `--ocr-cls-batch-size`: RapidOCR classifier batch size, default `32`.
- `--ocr-rec-batch-size`: RapidOCR recognizer batch size, default `64`.

## Batch Folder Scan

```powershell
python .\detection_detail_parallel\batch_scan_parallel.py `
  --input-dir .\Data\PDF `
  --out .\detection_detail_parallel\out_batch `
  --device cuda `
  --no-draw-bboxes
```

## Outputs

The final files mirror the original detector:

- `report.json`
- `regional_ocr_results.json`
- `regional_ocr_results.csv`
- `suspicious_regions.csv`
- `matching_debug.json`
- `gap_verification_results.csv`
- `table_debug.csv`

Additional file:

- `parallel_runtime.json`: OCR mode, batch sizes, primary/gap OCR timings, and
  model initialization timing.