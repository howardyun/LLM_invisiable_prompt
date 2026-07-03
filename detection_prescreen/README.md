# detection_prescreen

Fast two-stage screening for PDF prompt-injection risk.

Stage 1 uses only PyMuPDF and does not start OCR.  It looks for cheap signals:

- control-like instruction text in text blocks, metadata, annotations, or page streams
- near-white text, low-alpha text, off-page text, and invisible text rendering mode
- hidden-style text clusters that are worth checking visually

Stage 2 runs OCR only for candidates whose pre-screen score crosses the OCR
threshold.  Normal PDFs should usually finish without loading the GPU OCR model.

## Single PDF

```bash
bash detection_prescreen/run_prescreen.sh Data/PDF/DGA_IWQOS2025.pdf detection_prescreen/out 0 --ocr on-hit --device cuda
```

Equivalent Python command:

```powershell
python .\detection_prescreen\scan_pdf_prescreen.py `
  --pdf .\Data\PDF\DGA_IWQOS2025.pdf `
  --out .\detection_prescreen\out `
  --ocr on-hit `
  --device cuda
```

## Folder Batch

```powershell
python .\detection_prescreen\batch_prescreen.py `
  --input-dir .\Data\PDF `
  --out .\detection_prescreen\out_batch `
  --ocr on-hit `
  --device cuda
```

`--ocr on-hit` is the default.  Use `--ocr never` for a pure pre-screen pass,
or `--ocr always` when benchmarking the candidate OCR stage.

## Outputs

Batch mode now writes flat CSV tables at the output root by default:

- `documents.csv`: one row per PDF, with file metadata, risk score, candidate counts, top hit, OCR counts, and timing columns.
- `detections.csv`: one row per suspicious candidate, with page, bbox, reason, control groups/snippets, OCR visibility, and hidden-verification columns.
- `pages.csv`: one row per scanned page, with page-level candidate and extracted-text stats.
- `prescreen_summary.csv` / `prescreen_summary.json`: compact backward-compatible run summary.

`--output-layout csv` is the default and avoids creating one result folder per PDF. Use
`--output-layout legacy` or `--output-layout both` when you also want the older per-PDF
`prescreen_report.json`, `prescreen_candidates.csv`, and OCR verification files for debugging.
