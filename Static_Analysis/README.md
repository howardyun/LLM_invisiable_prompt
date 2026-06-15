# Static PDF Injection Scanner

Fast static scanner for implicit PDF prompt-injection candidates. It does not use OCR, VLM, page segmentation, or visual semantic comparison. It scans PDF-internal objects that common LLM document loaders may consume.

## Usage

Run from the repository root with the existing virtual environment:

```bash
.\venv\Scripts\python.exe -m Static_Analysis.pdf_static_scan scan --input .\Detection\LocalData\zero-width.pdf --output .\Static_Analysis\sample_findings.csv --output-problem-csv .\Static_Analysis\sample_problem_sentences.csv
```

Batch scan:

```bash
.\venv\Scripts\python.exe -m Static_Analysis.pdf_static_scan batch --input-dir .\Detection\LocalData --loader generic_t1 --output-csv .\Static_Analysis\static_summary.csv --output-findings-csv .\Static_Analysis\static_findings.csv --output-problem-csv .\Static_Analysis\static_problem_sentences.csv --jobs 8
```

Scan an arXiv-style date tree and write one output folder per day:

```bash
.\venv\Scripts\python.exe .\Static_Analysis\scan_date_tree.py --input-root G:\arxiv_pdf --output-root D:\scan_output --layout month-date-pdfs --jobs 8
```

For each day folder, the script writes:

```text
output-root/May_2026/2026-05-10/summary.csv
output-root/May_2026/2026-05-10/findings.csv
output-root/May_2026/2026-05-10/problem_sentences.csv
output-root/manifest.csv
```

The scanner also supports the older `year/month/day` layout via `--layout year-month-day`; the default `--layout auto` detects both.

Compare several loader profiles while extracting each PDF only once:

```bash
.\venv\Scripts\python.exe -m Static_Analysis.pdf_static_scan batch --input-dir .\Detection\LocalData --loaders generic_t1,langchain_pypdf,unstructured_hires --output-findings-csv .\Static_Analysis\multi_findings.csv --output-problem-csv .\Static_Analysis\multi_problem_sentences.csv --jobs 8
```

For pypdf-specific text behavior, enable the optional parser-text channel:

```bash
.\venv\Scripts\python.exe -m Static_Analysis.pdf_static_scan scan --input .\Detection\LocalData\zero-width.pdf --loader langchain_pypdf --include-pypdf-text
```

If throughput is more important than render-mode/layer visibility hints, disable `get_texttrace()`:

```bash
.\venv\Scripts\python.exe -m Static_Analysis.pdf_static_scan batch --input-dir .\Detection\LocalData --output-findings-csv results.csv --disable-texttrace-visibility --jobs 8
```

## Output

Each report contains:

- `scan --output xxx.csv`: one row per control-intent finding
- `batch --output-csv`: one row per PDF summary
- `batch --output-findings-csv`: one row per control-intent finding across the corpus
- `batch --output-problem-csv`: deduplicated table of which PDF contains which suspicious sentence
- non-fatal parser/extractor errors are stored in the `error` column

The findings CSVs only keep rows with `control_intent_score >= 0.4` and an explicit control-intent signal such as a matched phrase, action, role, or output-format instruction. Low-value signals such as a standalone word like `invisible` are filtered out.

The scanner is designed for large corpora: bad PDFs are recorded in CSV, and batch mode supports multiprocessing.
