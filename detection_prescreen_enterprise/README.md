# detection_prescreen_enterprise

Enterprise-style parallel PDF pre-screening pipeline.

## Architecture

```text
PDF folder
  -> CPU pre-screen worker pool
  -> candidate queue
  -> single GPU OCR micro-batch worker
  -> per-PDF reports + enterprise summary
```

The CPU stage uses multiple processes because PyMuPDF pre-screening is cheap
and independent per PDF.  The OCR stage deliberately uses one GPU model
instance, so an RTX 3060 is not overloaded by many competing OCR processes.

## Run

```bash
bash detection_prescreen_enterprise/run_enterprise.sh Data/PDF detection_prescreen_enterprise/out --device cuda
```

Equivalent PowerShell:

```powershell
python .\detection_prescreen_enterprise\enterprise_batch.py `
  --input-dir .\Data\PDF `
  --out .\detection_prescreen_enterprise\out `
  --prescreen-workers 8 `
  --ocr on-hit `
  --device cuda
```

## Important Options

- `--prescreen-workers 8`: CPU worker processes for PyMuPDF-only screening.
- `--ocr on-hit`: run OCR only when pre-screen candidates need it.
- `--ocr never`: pure CPU pre-screen benchmark mode.
- `--ocr-micro-batch-candidates 64`: flush GPU OCR when queued candidates reach this size.
- `--max-ocr-candidates-per-pdf 50`: cap OCR work per PDF.

## Outputs

The default output layout is flat and batch-oriented:

- `documents.csv`: one row per PDF, with file metadata, risk score, candidate counts, top hit, OCR counts, and timing columns.
- `detections.csv`: one row per suspicious candidate, with page, bbox, reason, control groups/snippets, OCR visibility, and hidden-verification columns.
- `pages.csv`: one row per scanned page, with page-level candidate and extracted-text stats.
- `enterprise_summary.csv` / `enterprise_summary.json`: compact backward-compatible run summary.

`--output-layout csv` is the default and avoids creating one result folder per PDF. Use
`--output-layout legacy` or `--output-layout both` when you also want the older per-PDF
`prescreen_report.json`, `prescreen_candidates.csv`, and OCR verification files for debugging.
